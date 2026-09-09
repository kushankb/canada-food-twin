"""
attach_geometry.py — resolve map geometry for the Canada-scoped edge set.

Why this exists: the paper's edge table (ForPaper/Data_Maps/All_FoodFlows_withlinestrings.
parquet) only covers 31.6% of the geo-edges the Canadian routes actually use -- 53.1% if you
also try the reversed edge-id orientation. It is a filtered paper product, not the full
network graph, so it is the WRONG geometry source for this app.

The right source is the original infrastructure network, which resolves 99.7% of Canadian
edges:
    road/RoadNodes_infrastructure.csv          node_id, iso3, lon, lat   (701 MB, grep-able)
    rail/RailNodes_infrastructure.csv          node_id, asset_type, iso3, lon, lat
    IWW/IWWNodes_infrastructure.csv            same shape
    Admin_regions/admin_centroids.gpkg         admin-1 centroids (CAN.12_1 style endpoints)
    Maritime/edges_maritime_corrected.gpkg     maritime lines

Edge ids are "<nodeA>-<nodeB>", so a straight segment between the two node coordinates is
enough for a flow map at national scale. For true road polylines upgrade to
road/RoadEdges_Complete_infrastructure.csv.gz (5.5 GB, edge_id + WKB geometry, keyed on the
same ids) -- same join, heavier scan.

Run: python3 canada-food-twin/scripts/attach_geometry.py --tag wheat_and_products
"""

import argparse
import json
import os
import sqlite3
import struct
import subprocess
import sys

import pandas as pd

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REPO_ROOT = os.path.dirname(BASE)
NET = os.path.join(REPO_ROOT, "Input", "Jasper_testdata", "Infrastructure_network",
                   "Infrastructure_networks")
ADMIN_GPKG = os.path.join(REPO_ROOT, "Input", "Jasper_testdata", "Infrastructure_network",
                          "Admin_regions", "admin_centroids.gpkg")
OUT_DIR = os.path.join(BASE, "data")
MARITIME_NODES = os.path.join(NET, "Maritime", "nodes_maritime.gpkg")
CACHE = os.path.join(OUT_DIR, "_nodes_cache")

NODE_FILES = [
    ("road", os.path.join(NET, "road", "RoadNodes_infrastructure.csv"),
     ["idx", "node_id", "iso3", "lon", "lat"]),
    ("rail", os.path.join(NET, "rail", "RailNodes_infrastructure.csv"),
     ["idx", "node_id", "asset_type", "iso3", "lon", "lat"]),
    ("iww", os.path.join(NET, "IWW", "IWWNodes_infrastructure.csv"),
     ["idx", "node_id", "asset_type", "iso3", "lon", "lat"]),
]


def load_nodes(isos=("CAN", "USA")):
    """grep the national slices out of the big node CSVs (0.2s vs minutes for a full parse).

    USA is included by default: Canada's land border crossings are among its most critical
    food infrastructure, and those edges have a US node on one end."""
    os.makedirs(CACHE, exist_ok=True)
    frames = []
    for iso in isos:
      for kind, path, cols in NODE_FILES:
        if not os.path.exists(path):
            print(f"  ! missing {path}", file=sys.stderr)
            continue
        cached = os.path.join(CACHE, f"{kind}_nodes_{iso}.csv")
        if not os.path.exists(cached):
            with open(cached, "w") as fh:
                subprocess.run(["grep", f",{iso},", path], stdout=fh, check=False)
        if os.path.getsize(cached) == 0:
            continue
        df = pd.read_csv(cached, names=cols, header=None)
        frames.append(df[["node_id", "lon", "lat"]])
        print(f"  {kind:<5} nodes ({iso}): {len(df):,}")
    if not frames:
        sys.exit("No node coordinates found.")
    return pd.concat(frames).drop_duplicates("node_id").set_index("node_id")


def gpkg_points(path, table=None):
    """Read point geometries straight out of a GeoPackage via sqlite3.

    The local geopandas/shapely stack is broken (shapely 1.x vs geopandas 2.x expectations),
    and a GPKG is just SQLite: a small header then standard WKB. Parsing it directly avoids
    the dependency entirely.
    """
    if not os.path.exists(path):
        return {}
    con = sqlite3.connect(path)
    try:
        tables = [r[0] for r in con.execute("select table_name from gpkg_contents")]
    except sqlite3.DatabaseError:
        return {}
    if table is None:
        table = tables[0] if tables else None
    if table is None:
        return {}
    cols = [r[1] for r in con.execute(f'PRAGMA table_info("{table}")')]
    geom_col = "geom" if "geom" in cols else ("geometry" if "geometry" in cols else None)
    id_col = next((c for c in ("id", "node_id", "ID", "GID_1", "gid_1", "admin_id", "name")
                   if c in cols), None)
    if geom_col is None or id_col is None:
        return {}

    if "latitude" in cols and "longitude" in cols:
        return {str(i): (float(lon), float(lat)) for i, lon, lat in
                con.execute(f'select "{id_col}", longitude, latitude from "{table}"')
                if lon is not None and lat is not None}

    out = {}
    env_size = {0: 0, 1: 32, 2: 48, 3: 48, 4: 64}
    for _id, blob in con.execute(f'select "{id_col}", "{geom_col}" from "{table}"'):
        if blob is None:
            continue
        flags = blob[3]
        wkb = blob[8 + env_size.get((flags >> 1) & 0x07, 0):]
        if not wkb:
            continue
        bo = "<" if wkb[0] == 1 else ">"
        gtype = struct.unpack(bo + "I", wkb[1:5])[0] % 1000
        if gtype == 1:  # Point
            x, y = struct.unpack(bo + "dd", wkb[5:21])
            out[str(_id)] = (x, y)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--tag", default="wheat_and_products")
    ap.add_argument("--scopes", default="canada,maritime_port")
    args = ap.parse_args()

    edges_path = os.path.join(OUT_DIR, f"canada_edges_{args.tag}.csv")
    if not os.path.exists(edges_path):
        sys.exit(f"Run extract_canada_flows.py first: {edges_path} not found")

    e = pd.read_csv(edges_path)
    scopes = [s.strip() for s in args.scopes.split(",")]
    e = e[e.scope.isin(scopes)]
    print(f"edges in scope {scopes}: {len(e):,} rows, {e.edge_id.nunique():,} unique")

    print("loading network nodes ...")
    nodes = load_nodes()
    coords = {k: (lo, la) for k, lo, la in
              zip(nodes.index, nodes.lon.values, nodes.lat.values)}
    maritime = gpkg_points(MARITIME_NODES)
    if maritime:
        print(f"  maritime nodes: {len(maritime):,}")
    coords.update(maritime)

    admin = gpkg_points(ADMIN_GPKG)
    if admin:
        print(f"  admin centroids: {len(admin):,}")
    coords.update(admin)

    rows, unresolved = [], []
    for eid in e.edge_id.unique():
        if "-" not in eid:
            unresolved.append(eid)
            continue
        a, b = eid.split("-", 1)
        pa, pb = coords.get(a), coords.get(b)
        if pa and pb:
            rows.append((eid, round(pa[0], 5), round(pa[1], 5),
                         round(pb[0], 5), round(pb[1], 5)))
        else:
            unresolved.append(eid)

    geo = pd.DataFrame(rows, columns=["edge_id", "lon_a", "lat_a", "lon_b", "lat_b"])
    out = os.path.join(OUT_DIR, f"canada_edge_geometry_{args.tag}.csv")
    geo.to_csv(out, index=False)

    total = e.edge_id.nunique()
    pct = len(geo) / total * 100 if total else 0
    print(f"\nresolved geometry: {len(geo):,} / {total:,}  ({pct:.1f}%)")
    print(f"unresolved: {len(unresolved):,}")
    if unresolved:
        print("  sample:", unresolved[:5])
    print(f"wrote {out}")

    meta = {"tag": args.tag, "scopes": scopes, "unique_edges": int(total),
            "resolved": int(len(geo)), "pct_resolved": round(pct, 2),
            "unresolved_sample": unresolved[:20],
            "geometry_source": "Infrastructure_networks node coordinates (straight segments); "
                               "upgrade to RoadEdges_Complete_infrastructure.csv.gz for true polylines",
            "note": "ForPaper All_FoodFlows_withlinestrings covers only 31.6% of these edges "
                    "(53.1% allowing reversed orientation) and must not be used as the source"}
    with open(os.path.join(OUT_DIR, f"canada_geometry_meta_{args.tag}.json"), "w") as fh:
        json.dump(meta, fh, indent=2)


if __name__ == "__main__":
    main()

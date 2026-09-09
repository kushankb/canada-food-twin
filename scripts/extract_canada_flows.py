"""
extract_canada_flows.py — Canada-scoped food flow + infrastructure criticality extraction (V8).

Unlike the global app's preprocess_data_v8.py, this KEEPS directionality. The V8
PostProcessed route files carry origin->destination admin-1 pairs together with the full
list of geo-edges each journey traverses, so imports and exports can be separated properly
and there is no ~46x destination multi-counting.

Source layout (Output/Version8/PostProcessed/<dataset>/<peri>/Tonnage/foodgroup1/Flows_*.csv.gz):
    from_id_admin, to_id_admin, flow_value, mode, segment_order, paths

Five flow types, one dataset each:
    sea_dom   Data_Sea_IncludingHinterland_Domestic     (hinterland + maritime legs)
    sea_re    Data_Sea_IncludingHinterland_ReExports
    land_dom  Data_Land_Domestic
    land_re   Data_Land_ReExports
    within    Data_WithinCountry

UNITS (validated against combined_commodity_df_allmods_pop.parquet):
    flow_value  is KILOGRAMS  (Canada wheat exports -> 28.9 Mt; global -> 2,198 kcal/cap/day)
    factors     are kcal per KG, and kg protein / kg fat per KG of product
    Nutrient factors are exact per (commodity x ORIGIN country) -- CV = 0.0 across 7,725
    groups. Keying on commodity alone is WRONG (CV up to 1.88).

Two data traps this script handles:
  1. The .csv.gz files are concatenations that repeat the header row mid-file.
  2. flow_value is REPEATED on every segment row of a journey. Dedupe per O-D for trade
     totals; for edge throughput add the journey's flow once per distinct edge.

Outputs (canada-food-twin/data/):
    canada_od_<tag>.csv       origin->destination trade, one row per O-D x commodity x flow_type
    canada_edges_<tag>.csv    per-edge throughput (shippable scope, all commodities)
    _parts_<tag>/             per-commodity shippable edge detail (parquet)
    canada_summary_<tag>.json partners, concentration (HHI), coverage curves

Run:  python3 canada-food-twin/scripts/extract_canada_flows.py --commodity "Wheat and products"
"""

import argparse
import gc
import glob
import json
import os
import re
import sys
import time
from collections import defaultdict

import numpy as np
import pandas as pd

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REPO_ROOT = os.path.dirname(BASE)
V8 = os.path.join(REPO_ROOT, "Output", "Version8")
POST = os.path.join(V8, "PostProcessed")
COMBINED = os.path.join(V8, "ForPaper", "combined_commodity_df_allmods_pop.parquet")
OUT_DIR = os.path.join(BASE, "data")

ISO = "CAN"

# dataset dir -> flow_type label
DATASETS = {
    "Data_Sea_IncludingHinterland_Domestic": "sea_dom",
    "Data_Sea_IncludingHinterland_ReExports": "sea_re",
    "Data_Land_Domestic": "land_dom",
    "Data_Land_ReExports": "land_re",
    "Data_WithinCountry": "within",
}
PERI_GROUPS = ["grains", "nonperi_nongrain", "perishable"]

TOKEN_RE = re.compile(r"'([^']+)'")
ISO_RE = re.compile(r"_([A-Z]{3})(?:-|$)")


# --------------------------------------------------------------------------- helpers

def parse_paths(val):
    """Route cell is a stringified list. Two dialects appear in V8:
    comma-separated  "['a', 'b']"  and numpy-style  "['a' 'b']". Quoted-token
    extraction handles both. Bare "a,b," (Data_Land_*) has no quotes -> fall back."""
    if not isinstance(val, str) or not val:
        return []
    toks = TOKEN_RE.findall(val)
    if toks:
        return toks
    return [p for p in val.strip("[]").replace("'", "").split(",") if p.strip()]


def edge_scope(edge_id):
    """Where does this segment physically sit? Drives the coverage scoping decision:
    Canadian + maritime edges are the defensible modelling scope; foreign inland
    delivery networks explode the edge count (240k for one commodity) and we do not
    claim to model road criticality inside partner countries."""
    codes = ISO_RE.findall(edge_id)
    if ISO in codes:
        return "canada"
    # A port-* segment tied to a foreign land node (port339-road16967824_CHN) is that
    # country's hinterland, not the sea leg -- classify by country before by prefix.
    if codes:
        return "foreign"
    if edge_id.startswith("maritime") or "-maritime" in edge_id or edge_id.startswith("port"):
        return "maritime_port"
    return "foreign"


def infra_mode(edge_id):
    if edge_id.startswith("maritime") or "-maritime" in edge_id:
        return "maritime"
    if edge_id.startswith("port") or "port" in edge_id:
        return "port"
    if "rail" in edge_id:
        return "rail"
    if "IWW" in edge_id:
        return "iww"
    if "road" in edge_id:
        return "road"
    return "other"


def iso_of(admin_id):
    return admin_id.split(".")[0] if isinstance(admin_id, str) else ""


def hhi(shares):
    """Herfindahl-Hirschman index on fractional shares (0-1). 1.0 = single source."""
    s = np.asarray(list(shares), dtype=float)
    if s.sum() <= 0:
        return float("nan")
    s = s / s.sum()
    return float((s ** 2).sum())


def coverage_curve(values, thresholds=(0.80, 0.90, 0.95, 0.99)):
    v = np.sort(np.asarray(list(values), dtype=float))[::-1]
    if v.size == 0 or v.sum() <= 0:
        return {}
    c = np.cumsum(v) / v.sum()
    return {f"{int(t*100)}%": int(np.searchsorted(c, t) + 1) for t in thresholds}


# --------------------------------------------------------------- nutrient factor table

def build_nutrient_factors(cache_path):
    """(commodity, origin ISO3) -> kcal/kg, protein kg/kg, fat kg/kg.

    Exact, not approximate: Energy = flow * factor holds to floating point within each
    (commodity, origin) group, so this is a lossless tonnage->nutrition conversion."""
    if os.path.exists(cache_path):
        return pd.read_csv(cache_path)

    import pyarrow.parquet as pq

    cols = ["from_id", "commodity", "flow", "Energy (kcal)", "Protein (kg)", "Fat (kg)"]
    pf = pq.ParquetFile(COMBINED)
    parts = []
    for i in range(pf.metadata.num_row_groups):
        d = pf.read_row_group(i, columns=cols).to_pandas()
        d["from_iso3"] = d.from_id.str.split(".").str[0]
        parts.append(
            d.groupby(["commodity", "from_iso3"], observed=True)[
                ["flow", "Energy (kcal)", "Protein (kg)", "Fat (kg)"]
            ].sum()
        )
    g = pd.concat(parts).groupby(level=[0, 1]).sum()
    g = g[g.flow > 0]
    out = pd.DataFrame(
        {
            "kcal_per_kg": g["Energy (kcal)"] / g.flow,
            "protein_kg_per_kg": g["Protein (kg)"] / g.flow,
            "fat_kg_per_kg": g["Fat (kg)"] / g.flow,
        }
    ).reset_index()
    os.makedirs(os.path.dirname(cache_path), exist_ok=True)
    out.to_csv(cache_path, index=False)
    return out


# ------------------------------------------------------------------------ file discovery

def find_files(commodity=None):
    """Return [(path, flow_type, peri_group, commodity)]. Commodity comes from the filename;
    WithinCountry uses underscores where the others use spaces."""
    found = []
    for dataset, ftype in DATASETS.items():
        for peri in PERI_GROUPS:
            pat = os.path.join(POST, dataset, peri, "Tonnage", "foodgroup1", "*.csv.gz")
            for p in sorted(glob.glob(pat)):
                name = os.path.basename(p)[len("Flows_"):-len(".csv.gz")]
                name = name.replace("_directconnection", "").replace("_", " ").strip()
                if commodity and name.lower() != commodity.lower():
                    continue
                found.append((p, ftype, peri, name))
    return found


# ------------------------------------------------------------------------ core extraction

def process_file(path, ftype, commodity, chunksize, od_acc, edge_acc, stats):
    """Stream one route file, keeping only journeys that touch Canada.

    od_acc:   (from_admin, to_admin, commodity, ftype, direction) -> kg  [deduped per O-D]
    edge_acc: (edge_id, direction)                                -> kg  [per distinct edge]
    Both accumulators are per-commodity and are flushed to disk after each commodity, so
    memory stays flat across the full 78-commodity pass.
    """
    seen_od = set()
    reader = pd.read_csv(
        path,
        chunksize=chunksize,
        dtype=str,
        usecols=["from_id_admin", "to_id_admin", "flow_value", "mode", "segment_order", "paths"],
    )
    # Two V8 source files are truncated mid-stream (Barley and products; Fats, Animals, Raw
    # under Data_Sea_IncludingHinterland_Domestic). Salvage every complete row rather than
    # aborting the whole pass, and record the loss so it is visible in the summary.
    while True:
        try:
            ch = next(reader)
        except StopIteration:
            break
        except (EOFError, OSError, pd.errors.ParserError) as exc:
            stats["truncated_files"] += 1
            stats.setdefault("truncated_list", [])
            if isinstance(stats["truncated_list"], list):
                stats["truncated_list"].append(f"{os.path.basename(path)} ({type(exc).__name__})")
            break
        # trap 1: concatenated files repeat the header row mid-file
        ch = ch[ch.from_id_admin != "from_id_admin"]
        if ch.empty:
            continue
        o = ch.from_id_admin.str.split(".").str[0]
        d = ch.to_id_admin.str.split(".").str[0]
        mask = (o == ISO) | (d == ISO)
        sub = ch[mask]
        stats["rows_scanned"] += len(ch)
        if sub.empty:
            continue
        stats["rows_canada"] += len(sub)

        for row, oo, dd in zip(sub.itertuples(index=False), o[mask], d[mask]):
            try:
                kg = float(row.flow_value)
            except (TypeError, ValueError):
                continue
            if kg <= 0:
                continue

            if oo == ISO and dd == ISO:
                direction = "within"
            elif oo == ISO:
                direction = "export"
            else:
                direction = "import"

            # trap 2: flow_value repeats on every segment -> count the O-D once
            od_key = (row.from_id_admin, row.to_id_admin, commodity, ftype, direction)
            if od_key not in seen_od:
                seen_od.add(od_key)
                od_acc[od_key] += kg

            # edge throughput: the journey's tonnage passes over each distinct edge once
            for e in set(parse_paths(row.paths)):
                edge_acc[(e, direction)] += kg

    stats["files"] += 1


def od_frame(od_acc, fmap):
    od = pd.DataFrame(
        [(k[0], k[1], k[2], k[3], k[4], v) for k, v in od_acc.items()],
        columns=["from_admin", "to_admin", "commodity", "flow_type", "direction", "kg"],
    )
    if od.empty:
        return od.assign(from_iso3=[], to_iso3=[], tonnes=[], kcal=[], protein_kg=[], fat_kg=[])
    od["from_iso3"] = od.from_admin.map(iso_of)
    od["to_iso3"] = od.to_admin.map(iso_of)
    od["tonnes"] = od.kg / 1000.0
    fac = np.array([fmap.get((c, o), (np.nan, np.nan, np.nan))
                    for c, o in zip(od.commodity, od.from_iso3)])
    od["kcal"] = od.kg.values * fac[:, 0]
    od["protein_kg"] = od.kg.values * fac[:, 1]
    od["fat_kg"] = od.kg.values * fac[:, 2]
    return od


def edge_frame(edge_acc, commodity):
    e = pd.DataFrame([(k[0], k[1], v) for k, v in edge_acc.items()],
                     columns=["edge_id", "direction", "kg"])
    if e.empty:
        return e.assign(commodity=[], tonnes=[], scope=[], mode=[])
    e["commodity"] = commodity
    e["tonnes"] = e.kg / 1000.0
    e["scope"] = e.edge_id.map(edge_scope)
    e["mode"] = e.edge_id.map(infra_mode)
    return e


def summarise(od, edges_shippable, edges_foreign_count, stats, label, t0):
    summary = {
        "commodity": label,
        "units": {"tonnes": "metric tonnes", "kcal": "kilocalories",
                  "note": "source flow_value is kg; nutrient factors are per-kg "
                          "and exact per (commodity x origin country)"},
        "scan": {"rows_scanned": int(stats["rows_scanned"]),
                 "rows_canada": int(stats["rows_canada"]),
                 "files": int(stats["files"]),
                 "truncated_source_files": int(stats.get("truncated_files", 0)),
                 "truncated_list": stats.get("truncated_list", []),
                 "elapsed_sec": round(time.time() - t0, 1)},
        "od_rows_missing_nutrient_factor": int(od.kcal.isna().sum()) if len(od) else 0,
        "trade": {}, "partners": {}, "concentration": {},
        "top_commodities": {}, "edge_coverage": {},
        "foreign_edges_dropped_from_shippable": int(edges_foreign_count),
    }
    for direction in ("import", "export", "within"):
        sub = od[od.direction == direction]
        if sub.empty:
            continue
        summary["trade"][direction] = {
            "tonnes": round(float(sub.tonnes.sum()), 1),
            "kcal": float(np.nansum(sub.kcal)),
            "od_pairs": int(len(sub)),
            "by_flow_type": {k: round(float(v), 1)
                             for k, v in sub.groupby("flow_type").tonnes.sum().items()},
        }
        partner_col = "from_iso3" if direction == "import" else "to_iso3"
        p = sub.groupby(partner_col).tonnes.sum().sort_values(ascending=False)
        summary["partners"][direction] = {k: round(float(v), 1) for k, v in p.head(20).items()}
        total = float(p.sum())
        h = hhi(p.values)
        summary["concentration"][direction] = {
            "n_partners": int(len(p)), "hhi": round(h, 4),
            "effective_partners": round(1.0 / h, 2) if h and h > 0 else None,
            "top1_share": round(float(p.iloc[0] / total), 4) if total else None,
            "top3_share": round(float(p.head(3).sum() / total), 4) if total else None,
        }
        # per-commodity concentration: which commodities is Canada most exposed on?
        percom = {}
        for cname, grp in sub.groupby("commodity"):
            pp = grp.groupby(partner_col).tonnes.sum()
            if pp.sum() <= 0:
                continue
            hh = hhi(pp.values)
            percom[cname] = {
                "tonnes": round(float(pp.sum()), 1),
                "kcal": float(np.nansum(grp.kcal)),
                "n_partners": int(len(pp)), "hhi": round(hh, 4),
                "effective_partners": round(1.0 / hh, 2) if hh and hh > 0 else None,
                "top_partner": str(pp.idxmax()),
                "top_partner_share": round(float(pp.max() / pp.sum()), 4),
            }
        summary["top_commodities"][direction] = dict(
            sorted(percom.items(), key=lambda kv: -kv[1]["tonnes"])[:40])

    for direction in ("import", "export", "within"):
        sub = edges_shippable[edges_shippable.direction == direction]
        if sub.empty:
            continue
        block = {}
        for scope in ("canada", "maritime_port"):
            s = sub[sub.scope == scope]
            if not s.empty:
                block[scope] = {"edges": int(len(s)), "coverage": coverage_curve(s.kg.values)}
        block["SHIPPABLE_canada_plus_maritime"] = {
            "edges": int(len(sub)), "coverage": coverage_curve(sub.kg.values)}
        summary["edge_coverage"][direction] = block
    return summary


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--commodity", default="Wheat and products",
                    help='Single commodity, or "ALL" for the full 25 GB pass.')
    ap.add_argument("--chunksize", type=int, default=300_000)
    ap.add_argument("--tag", default=None, help="Output filename suffix.")
    ap.add_argument("--keep-foreign-parts", action="store_true",
                    help="Also persist per-edge foreign-territory detail (large).")
    args = ap.parse_args()

    commodity = None if args.commodity.upper() == "ALL" else args.commodity
    tag = args.tag or (re.sub(r"[^A-Za-z0-9]+", "_", args.commodity).strip("_").lower())
    os.makedirs(OUT_DIR, exist_ok=True)
    parts_dir = os.path.join(OUT_DIR, f"_parts_{tag}")
    os.makedirs(parts_dir, exist_ok=True)

    t0 = time.time()
    factors = build_nutrient_factors(os.path.join(OUT_DIR, "nutrient_factors.csv"))
    fmap = {(r.commodity, r.from_iso3): (r.kcal_per_kg, r.protein_kg_per_kg, r.fat_kg_per_kg)
            for r in factors.itertuples(index=False)}
    print(f"nutrient factors: {len(fmap):,} (commodity x origin)")

    files = find_files(commodity)
    if not files:
        sys.exit(f"No route files matched commodity={args.commodity!r}")

    by_commodity = defaultdict(list)
    for rec in files:
        by_commodity[rec[3]].append(rec)
    print(f"route files: {len(files)}  across {len(by_commodity)} commodities\n")

    # Cross-commodity accumulator is SHIPPABLE-ONLY, so it is bounded by the size of the
    # Canadian network (~350k nodes) rather than growing with commodity count.
    global_edges = defaultdict(float)
    od_parts, foreign_partner_rows = [], []
    stats = defaultdict(int)
    n_foreign_dropped = 0

    for ci, (cname, flist) in enumerate(sorted(by_commodity.items()), 1):
        od_acc, edge_acc = defaultdict(float), defaultdict(float)
        mb = sum(os.path.getsize(f[0]) for f in flist) / 1048576
        ts = time.time()
        print(f"[{ci}/{len(by_commodity)}] {cname[:44]:<44} {len(flist)} files {mb:8.1f} MB ...",
              end="", flush=True)
        for path, ftype, peri, cn in flist:
            process_file(path, ftype, cn, args.chunksize, od_acc, edge_acc, stats)

        od = od_frame(od_acc, fmap)
        e = edge_frame(edge_acc, cname)
        if not e.empty:
            ship = e[e.scope.isin(("canada", "maritime_port"))]
            n_foreign_dropped += int(len(e) - len(ship))
            for eid, dirn, kg in zip(ship.edge_id, ship.direction, ship.kg):
                global_edges[(eid, dirn)] += kg
            ship.drop(columns=["kg"]).to_parquet(
                os.path.join(parts_dir, f"edges_{ci:03d}.parquet"), index=False)
            if args.keep_foreign_parts:
                e[e.scope == "foreign"].drop(columns=["kg"]).to_parquet(
                    os.path.join(parts_dir, f"edges_foreign_{ci:03d}.parquet"), index=False)
        if not od.empty:
            od_parts.append(od.drop(columns=["kg"]))
        print(f" {time.time()-ts:5.0f}s  od={len(od):>6,} ship_edges={0 if e.empty else len(ship):>7,}")
        del od_acc, edge_acc, e
        gc.collect()

    # ------------------------------------------------------------------- merge
    od_all = pd.concat(od_parts, ignore_index=True) if od_parts else pd.DataFrame()
    od_path = os.path.join(OUT_DIR, f"canada_od_{tag}.csv")
    od_all.to_csv(od_path, index=False)

    ge = pd.DataFrame([(k[0], k[1], v) for k, v in global_edges.items()],
                      columns=["edge_id", "direction", "kg"])
    ge["tonnes"] = ge.kg / 1000.0
    ge["scope"] = ge.edge_id.map(edge_scope)
    ge["mode"] = ge.edge_id.map(infra_mode)
    ge = ge.sort_values("kg", ascending=False)
    edges_path = os.path.join(OUT_DIR, f"canada_edges_{tag}.csv")
    ge.drop(columns=["kg"]).to_csv(edges_path, index=False)

    summary = summarise(od_all, ge, n_foreign_dropped, stats, args.commodity, t0)
    sum_path = os.path.join(OUT_DIR, f"canada_summary_{tag}.json")
    with open(sum_path, "w") as f:
        json.dump(summary, f, indent=2)

    print(f"\nwrote {od_path}  ({len(od_all):,} rows)")
    print(f"wrote {edges_path}  ({len(ge):,} rows, all commodities combined)")
    print(f"wrote {parts_dir}/  (per-commodity shippable edge detail)")
    print(f"wrote {sum_path}")
    print(f"total elapsed {time.time()-t0:.0f}s")


if __name__ == "__main__":
    main()

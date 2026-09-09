"""
build_app_data_v2.py — Canada food twin, directional + food-group app payload.

Turns the Canada extraction into the app's shipped payload. Three decisions worth knowing
before changing anything here:

  1. FULL network. No calorie threshold: every Canada-linked edge ships. The payload stays
     small because edges move from JSON to a packed binary (`edges.bin`), ~37 bytes/edge
     instead of ~290. See PACK LAYOUT below.
  2. FOOD GROUPS. `data/food_groups.csv` maps all 82 FBS commodities onto 12 groups, and
     every aggregate -- partners, provinces, edges -- is cut by group as well as in total.
  3. NAME NORMALISATION. The source writes some commodities two ways ("Aquatic Animals,
     Others" and "Aquatic Animals  Others"). Left alone, one commodity becomes two and its
     concentration metrics are wrong. `norm_commodity` folds them back together.

Inputs (data/):
    canada_od_<tag>.csv              origin->destination trade, per commodity
    canada_edges_<tag>.csv           per-edge throughput
    _parts_<tag>/edges_*.parquet     per-edge, per-commodity detail
    canada_edge_geometry_<tag>.csv   edge_id -> endpoints
    food_groups.csv                  commodity -> food group

Outputs (public/data/):
    meta.json          coverage, units, caveats, headline totals by direction and group
    partners.json      partner concentration: overall, by food group, by commodity
    commodities.json   per-commodity dependence, tagged with its food group
    foodgroups.json    per-group concentration, partners, provinces, transport mix
    provinces.json     per-province trade, by group, with partners and commodities
    edges.bin          packed edge geometry + quantities + food-group mix
    edges_meta.json    the key to edges.bin: offsets, dtypes, code tables
    ec/<shard>.json    edge index -> commodities carried, sharded 256 ways and fetched
                       on demand: the map never needs it, only the detail panel does

Run: python3 scripts/build_app_data_v2.py --tag all
"""

import argparse
import glob
import json
import os
import re

import numpy as np
import pandas as pd

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(BASE, "data")
OUT = os.path.join(BASE, "public", "data")

DIRECTIONS = ("import", "export", "within")

# GADM level-1 codes are alphabetical. Verified against the data: CAN.12_1 carries 12.2 Mt of
# wheat exports (Saskatchewan), CAN.9_1 takes the largest import tonnage (Ontario).
PROVINCES = {
    "CAN.1_1": ("Alberta", "AB"), "CAN.2_1": ("British Columbia", "BC"),
    "CAN.3_1": ("Manitoba", "MB"), "CAN.4_1": ("New Brunswick", "NB"),
    "CAN.5_1": ("Newfoundland and Labrador", "NL"), "CAN.6_1": ("Northwest Territories", "NT"),
    "CAN.7_1": ("Nova Scotia", "NS"), "CAN.8_1": ("Nunavut", "NU"),
    "CAN.9_1": ("Ontario", "ON"), "CAN.10_1": ("Prince Edward Island", "PE"),
    "CAN.11_1": ("Quebec", "QC"), "CAN.12_1": ("Saskatchewan", "SK"),
    "CAN.13_1": ("Yukon", "YT"),
}

# Order is the wire format for edges.bin food-group shares. Never reorder without rebuilding.
FOOD_GROUPS = [
    "Grains", "Fruits", "Vegetables", "Meat and Fish", "Dairy and Eggs", "Oils and Oilseed",
    "Pulses", "Starchy Roots", "Treenuts", "Sugar and Sweeteners", "Stimulants and Spices",
    "Other",
]
MODES = ["road", "rail", "maritime", "port", "other"]
SCOPES = ["canada", "maritime_port", "other"]

# Shard count for the per-edge commodity detail. 256 keeps each file ~55 KB.
EC_SHARDS = 256


def norm_commodity(s):
    """Fold the source's double-space variants back onto their comma spelling."""
    return re.sub(r"\s{2,}", ", ", str(s)).strip()


def hhi(v):
    v = np.asarray(v, dtype=float)
    if v.sum() <= 0:
        return float("nan")
    v = v / v.sum()
    return float((v ** 2).sum())


def concentration(series, top_n=25):
    """Dependence / diversification block for one partner-tonnage series."""
    s = series[series > 0].sort_values(ascending=False)
    if s.empty:
        return None
    tot = float(s.sum())
    h = hhi(s.values)
    c = np.cumsum(s.values) / tot
    return {
        "total_tonnes": round(tot, 1),
        "n_partners": int(len(s)),
        "hhi": round(h, 4),
        "effective_partners": round(1.0 / h, 2) if h > 0 else None,
        "top1": {"iso3": str(s.index[0]), "share": round(float(s.iloc[0] / tot), 4)},
        "top3_share": round(float(s.head(3).sum() / tot), 4),
        "top5_share": round(float(s.head(5).sum() / tot), 4),
        "partners_for_50pct": int(np.searchsorted(c, 0.50) + 1),
        "partners_for_90pct": int(np.searchsorted(c, 0.90) + 1),
        "top_partners": [{"iso3": str(k), "tonnes": round(float(v), 1),
                          "share": round(float(v / tot), 4)}
                         for k, v in s.head(top_n).items()],
    }


def share_list(series, top_n=12, key="k"):
    """Ranked share breakdown, e.g. province -> food group mix."""
    s = series[series > 0].sort_values(ascending=False)
    if s.empty:
        return []
    tot = float(s.sum())
    return [{key: str(k), "tonnes": round(float(v), 1), "share": round(float(v / tot), 4)}
            for k, v in s.head(top_n).items()]


def load_inputs(tag):
    xw = pd.read_csv(os.path.join(DATA, "food_groups.csv"))
    fg_of = dict(zip(xw.commodity, xw.food_group))

    od = pd.read_csv(os.path.join(DATA, f"canada_od_{tag}.csv"))
    od["commodity"] = od.commodity.map(norm_commodity)
    od["food_group"] = od.commodity.map(fg_of).fillna("Other")
    # The Canadian end of the journey: where the food lands, or where it left from.
    od["ca_admin"] = np.where(od.direction == "import", od.to_admin, od.from_admin)
    od["partner"] = np.where(od.direction == "import", od.from_iso3, od.to_iso3)

    edges = pd.read_csv(os.path.join(DATA, f"canada_edges_{tag}.csv"))
    geo_path = os.path.join(DATA, f"canada_edge_geometry_{tag}.csv")
    geo = pd.read_csv(geo_path) if os.path.exists(geo_path) else pd.DataFrame()

    parts = sorted(glob.glob(os.path.join(DATA, f"_parts_{tag}", "edges_[0-9]*.parquet")))
    ec = (pd.concat([pd.read_parquet(p) for p in parts], ignore_index=True)
          if parts else pd.DataFrame())
    if not ec.empty:
        ec["commodity"] = ec.commodity.map(norm_commodity)
        ec["food_group"] = ec.commodity.map(fg_of).fillna("Other")

    print(f"O-D {len(od):,} rows | edges {len(edges):,} | geometry {len(geo):,} | "
          f"per-commodity {len(ec):,} from {len(parts)} parts")
    return od, edges, geo, ec, fg_of


def energy_per_tonne(od):
    """commodity x direction -> kcal/tonne, weighted by Canada's actual origin mix."""
    out = {}
    for (cname, d), g in od.groupby(["commodity", "direction"]):
        t = float(g.tonnes.sum())
        k = float(np.nansum(g.kcal))
        if t > 0 and np.isfinite(k):
            out[(cname, d)] = k / t
    return out


def build_partners(od):
    """Partner concentration per direction: overall, per food group, per commodity."""
    partners = {}
    for d in DIRECTIONS:
        sub = od[od.direction == d]
        if sub.empty:
            continue
        block = {"overall": concentration(sub.groupby("partner").tonnes.sum()),
                 "by_food_group": {}, "by_commodity": {}}
        for g, gg in sub.groupby("food_group"):
            b = concentration(gg.groupby("partner").tonnes.sum())
            if b:
                b["kcal"] = float(np.nansum(gg.kcal))
                block["by_food_group"][g] = b
        for cname, gg in sub.groupby("commodity"):
            b = concentration(gg.groupby("partner").tonnes.sum(), top_n=15)
            if b:
                b["kcal"] = float(np.nansum(gg.kcal))
                b["food_group"] = gg.food_group.iloc[0]
                block["by_commodity"][cname] = b
        partners[d] = block
    return partners


def build_commodities(partners):
    """Per-commodity dependence, ranked by calorie-weighted concentration."""
    commodities = {}
    for d in ("import", "export"):
        if d not in partners:
            continue
        rows = [{
            "commodity": cname,
            "food_group": b["food_group"],
            "tonnes": b["total_tonnes"],
            "kcal": b.get("kcal"),
            "n_partners": b["n_partners"],
            "hhi": b["hhi"],
            "effective_partners": b["effective_partners"],
            "top_partner": b["top1"]["iso3"],
            "top_partner_share": b["top1"]["share"],
            "partners_for_90pct": b["partners_for_90pct"],
        } for cname, b in partners[d]["by_commodity"].items()]
        rows.sort(key=lambda r: -(r["kcal"] or 0))
        tot_k = sum(r["kcal"] or 0 for r in rows) or 1.0
        for r in rows:
            r["calorie_share"] = round((r["kcal"] or 0) / tot_k, 5)
            # Big AND concentrated is the risk; either alone is not.
            r["exposure_index"] = round(r["calorie_share"] * (r["hhi"] or 0), 6)
        commodities[d] = rows
    return commodities


def build_foodgroups(od, partners, ec):
    """Per-group totals, concentration, province mix and transport mix."""
    mode_by_group = {}
    if not ec.empty and "mode" in ec.columns:
        mode_by_group = {
            (d, g): gg.groupby("mode").tonnes.sum()
            for (d, g), gg in ec.groupby(["direction", "food_group"])
        }
    out = {}
    for d in DIRECTIONS:
        sub = od[od.direction == d]
        if sub.empty:
            continue
        tot_t = float(sub.tonnes.sum()) or 1.0
        tot_k = float(np.nansum(sub.kcal)) or 1.0
        rows = []
        for g, gg in sub.groupby("food_group"):
            b = (partners.get(d, {}).get("by_food_group", {}) or {}).get(g)
            k = float(np.nansum(gg.kcal))
            rows.append({
                "food_group": g,
                "tonnes": round(float(gg.tonnes.sum()), 1),
                "kcal": k,
                "tonne_share": round(float(gg.tonnes.sum()) / tot_t, 4),
                "calorie_share": round(k / tot_k, 4),
                "n_commodities": int(gg.commodity.nunique()),
                "n_partners": (b or {}).get("n_partners"),
                "hhi": (b or {}).get("hhi"),
                "effective_partners": (b or {}).get("effective_partners"),
                "top_partner": ((b or {}).get("top1") or {}).get("iso3"),
                "top_partner_share": ((b or {}).get("top1") or {}).get("share"),
                "partners_for_90pct": (b or {}).get("partners_for_90pct"),
                "top_partners": (b or {}).get("top_partners", [])[:10],
                "provinces": share_list(gg.groupby("ca_admin").tonnes.sum(), 13, key="admin"),
                "commodities": share_list(gg.groupby("commodity").tonnes.sum(), 10, key="commodity"),
                "modes": share_list(mode_by_group.get((d, g), pd.Series(dtype=float)), 6, key="mode"),
            })
        rows.sort(key=lambda r: -(r["kcal"] or 0))
        for r in rows:
            r["exposure_index"] = round((r["calorie_share"] or 0) * (r["hhi"] or 0), 6)
        out[d] = rows
    return out


def build_provinces(od):
    """Which regions matter, per direction: volume, group mix, partners, commodities."""
    out = {}
    for d in DIRECTIONS:
        sub = od[od.direction == d]
        if sub.empty:
            continue
        tot_t = float(sub.tonnes.sum()) or 1.0
        rows = []
        for admin, gg in sub.groupby("ca_admin"):
            if admin not in PROVINCES:
                continue
            name, code = PROVINCES[admin]
            conc = concentration(gg.groupby("partner").tonnes.sum(), top_n=10)
            rows.append({
                "admin": admin, "name": name, "code": code,
                "tonnes": round(float(gg.tonnes.sum()), 1),
                "kcal": float(np.nansum(gg.kcal)),
                "share_of_national": round(float(gg.tonnes.sum()) / tot_t, 4),
                "n_partners": (conc or {}).get("n_partners"),
                "hhi": (conc or {}).get("hhi"),
                "effective_partners": (conc or {}).get("effective_partners"),
                "top_partner": ((conc or {}).get("top1") or {}).get("iso3"),
                "top_partner_share": ((conc or {}).get("top1") or {}).get("share"),
                "top_partners": (conc or {}).get("top_partners", []),
                "food_groups": share_list(gg.groupby("food_group").tonnes.sum(), 12, key="food_group"),
                "commodities": share_list(gg.groupby("commodity").tonnes.sum(), 10, key="commodity"),
            })
        rows.sort(key=lambda r: -r["tonnes"])
        out[d] = rows
    return out


def pack_edges(edges, geo, ec, kcal_per_t):
    """Pack the full edge network into a binary buffer.

    PACK LAYOUT -- one contiguous little-endian buffer, N edges, sections in this order:
        coords    float32[N*4]   lon_a, lat_a, lon_b, lat_b
        tonnes    float32[N]
        kcal      float32[N]     ~1e13 magnitudes; float32 keeps ~7 significant digits
        dir       uint8[N]       index into DIRECTIONS
        mode      uint8[N]       index into MODES
        scope     uint8[N]       index into SCOPES
        fg        uint8[N*12]    food-group tonnage share, 0-255, order = FOOD_GROUPS
        topc      uint16[N]      index into the commodity code table
    Edges with no resolved geometry are dropped: they cannot be drawn and every consumer of
    this file is a map layer.
    """
    e = edges.copy()
    e["commodity"] = None  # edges table is already commodity-aggregated

    if not ec.empty:
        ec = ec.copy()
        ec["kcal"] = [t * kcal_per_t.get((c, d), np.nan)
                      for t, c, d in zip(ec.tonnes, ec.commodity, ec.direction)]
        agg = ec.groupby(["edge_id", "direction"], as_index=False).agg(kcal=("kcal", "sum"))
        e = e.drop(columns=[c for c in ("kcal",) if c in e.columns])
        e = e.merge(agg, on=["edge_id", "direction"], how="left")

    if not geo.empty:
        e = e.merge(geo, on="edge_id", how="left")

    before = len(e)
    e = e[e.lon_a.notna() & e.lon_b.notna()].reset_index(drop=True)
    dropped = before - len(e)

    # food-group mix per (edge, direction), as shares of that edge's tonnage
    fg = np.zeros((len(e), len(FOOD_GROUPS)), dtype=np.uint8)
    topc = np.zeros(len(e), dtype=np.uint16)
    commodity_codes = []
    if not ec.empty:
        pos = {(r.edge_id, r.direction): i for i, r in enumerate(e.itertuples(index=False))}
        gidx = {g: i for i, g in enumerate(FOOD_GROUPS)}
        grp = ec.groupby(["edge_id", "direction", "food_group"], as_index=False).tonnes.sum()
        acc = np.zeros((len(e), len(FOOD_GROUPS)), dtype=np.float64)
        for r in grp.itertuples(index=False):
            i = pos.get((r.edge_id, r.direction))
            if i is not None:
                acc[i, gidx.get(r.food_group, len(FOOD_GROUPS) - 1)] += r.tonnes
        tot = acc.sum(axis=1, keepdims=True)
        with np.errstate(invalid="ignore", divide="ignore"):
            fg = np.nan_to_num(acc / np.where(tot > 0, tot, np.nan) * 255).astype(np.uint8)

        top = (ec.sort_values("tonnes", ascending=False)
                 .drop_duplicates(["edge_id", "direction"]))
        commodity_codes = sorted(ec.commodity.unique())
        cidx = {c: i for i, c in enumerate(commodity_codes)}
        for r in top.itertuples(index=False):
            i = pos.get((r.edge_id, r.direction))
            if i is not None:
                topc[i] = cidx.get(r.commodity, 0)

    dir_c = e.direction.map({d: i for i, d in enumerate(DIRECTIONS)}).fillna(0).astype(np.uint8)
    mode_c = e["mode"].map({m: i for i, m in enumerate(MODES)}).fillna(len(MODES) - 1).astype(np.uint8)
    scope_c = e.scope.map({s: i for i, s in enumerate(SCOPES)}).fillna(len(SCOPES) - 1).astype(np.uint8)

    coords = np.stack([e.lon_a, e.lat_a, e.lon_b, e.lat_b], axis=1).astype(np.float32)
    tonnes = e.tonnes.to_numpy(dtype=np.float32)
    kcal = e.get("kcal", pd.Series(np.zeros(len(e)))).fillna(0).to_numpy(dtype=np.float32)

    buf = b"".join([coords.tobytes(), tonnes.tobytes(), kcal.tobytes(),
                    dir_c.to_numpy().tobytes(), mode_c.to_numpy().tobytes(),
                    scope_c.to_numpy().tobytes(), fg.tobytes(), topc.tobytes()])

    n = len(e)
    off, sections = 0, {}
    for name, dtype, count in (("coords", "float32", n * 4), ("tonnes", "float32", n),
                               ("kcal", "float32", n), ("dir", "uint8", n),
                               ("mode", "uint8", n), ("scope", "uint8", n),
                               ("fg", "uint8", n * len(FOOD_GROUPS)), ("topc", "uint16", n)):
        width = {"float32": 4, "uint8": 1, "uint16": 2}[dtype]
        sections[name] = {"offset": off, "dtype": dtype, "count": count}
        off += count * width

    meta = {
        "count": n,
        "byteLength": off,
        "sections": sections,
        "codes": {"direction": list(DIRECTIONS), "mode": MODES, "scope": SCOPES,
                  "foodGroup": FOOD_GROUPS, "commodity": commodity_codes},
        "note": "little-endian; fg is tonnage share 0-255 per food group, order = codes.foodGroup",
        "dropped_no_geometry": int(dropped),
    }
    return buf, meta, e


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--tag", default="all")
    args = ap.parse_args()
    os.makedirs(OUT, exist_ok=True)

    od, edges, geo, ec, _ = load_inputs(args.tag)
    kcal_per_t = energy_per_tonne(od)

    partners = build_partners(od)
    commodities = build_commodities(partners)
    foodgroups = build_foodgroups(od, partners, ec)
    provinces = build_provinces(od)

    buf, edges_meta, kept = pack_edges(edges, geo, ec, kcal_per_t)
    with open(os.path.join(OUT, "edges.bin"), "wb") as f:
        f.write(buf)
    print(f"packed {edges_meta['count']:,} edges "
          f"({edges_meta['byteLength']/1048576:.2f} MB, "
          f"{edges_meta['byteLength']/max(edges_meta['count'],1):.0f} bytes/edge); "
          f"dropped {edges_meta['dropped_no_geometry']:,} without geometry")

    # Edge index -> commodities carried. Whole-file this is ~14 MB, far bigger than the
    # network itself, and the map never reads it -- only the detail panel, one edge at a
    # time. So it ships as EC_SHARDS files keyed by `index % EC_SHARDS`; the app fetches
    # the single ~55 KB shard for the edge that was clicked.
    shards = [{} for _ in range(EC_SHARDS)]
    if not ec.empty:
        pos = {(r.edge_id, r.direction): i for i, r in enumerate(kept.itertuples(index=False))}
        sel = ec[ec.edge_id.isin(set(kept.edge_id))]
        for (eid, d), g in sel.groupby(["edge_id", "direction"]):
            i = pos.get((eid, d))
            if i is None:
                continue
            g = g.sort_values("tonnes", ascending=False).head(6)
            tot = float(g.tonnes.sum()) or 1.0
            shards[i % EC_SHARDS][str(i)] = [{"c": c, "s": round(float(t / tot), 3)}
                                             for c, t in zip(g.commodity, g.tonnes)]
    ec_dir = os.path.join(OUT, "ec")
    os.makedirs(ec_dir, exist_ok=True)
    for old in glob.glob(os.path.join(ec_dir, "*.json")):
        os.remove(old)
    for i, sh in enumerate(shards):
        with open(os.path.join(ec_dir, f"{i}.json"), "w") as f:
            json.dump(sh, f, separators=(",", ":"))
    shard_bytes = sum(os.path.getsize(os.path.join(ec_dir, f"{i}.json")) for i in range(EC_SHARDS))
    print(f"wrote ec/ {EC_SHARDS} shards       {shard_bytes/1048576:7.2f} MB total, "
          f"{shard_bytes/EC_SHARDS/1024:.0f} KB each")
    edges_meta["ecShards"] = EC_SHARDS

    meta = {
        "country": "CAN",
        "tag": args.tag,
        "coverage": "full network — no calorie threshold applied",
        "units": {"tonnes": "metric tonnes", "kcal": "kilocalories"},
        "foodGroups": FOOD_GROUPS,
        "provinces": [{"admin": k, "name": v[0], "code": v[1]} for k, v in PROVINCES.items()],
        "headline": {
            d: {"tonnes": round(float(od[od.direction == d].tonnes.sum()), 1),
                "kcal": float(np.nansum(od[od.direction == d].kcal)),
                "commodities": int(od[od.direction == d].commodity.nunique()),
                "food_groups": int(od[od.direction == d].food_group.nunique()),
                "partners": int(od[od.direction == d].partner.nunique()),
                "provinces": int(od[od.direction == d].ca_admin.isin(PROVINCES).sum() > 0
                                 and od[od.direction == d].ca_admin.nunique()),
                "hhi": (partners.get(d, {}).get("overall") or {}).get("hhi"),
                "effective_partners": (partners.get(d, {}).get("overall") or {}).get("effective_partners")}
            for d in DIRECTIONS if (od.direction == d).any()
        },
        "caveats": [
            "Per-edge quantities are directional throughput for Canada-linked journeys only, "
            "derived from origin->destination routes -- not the undirected global totals used "
            "by the global app, and not subject to its ~46x destination multi-counting.",
            "Edge scope is Canadian territory plus maritime and port legs. Inland delivery "
            "inside partner countries is deliberately excluded: we do not model foreign road "
            "criticality.",
            "Criticality here is throughput share, not a no-alternative-route counterfactual. "
            "A high-throughput edge is not automatically irreplaceable.",
            "Concentration (HHI, effective partners) is measured on tonnage by partner "
            "country, so it describes sourcing breadth, not substitutability: two suppliers "
            "in one climate zone count as two.",
            "Within-Canada domestic distribution is sparse in the source "
            "(Data_WithinCountry covers surplus->deficit redistribution only).",
            "Route-level totals fall ~10% below O-D totals: some flows have no routable path.",
            "Provinces are the Canadian end of each journey — destination for imports, origin "
            "for exports — not the province of final consumption or of primary production.",
        ],
    }

    for name, obj in (("meta.json", meta), ("partners.json", partners),
                      ("commodities.json", commodities), ("foodgroups.json", foodgroups),
                      ("provinces.json", provinces), ("edges_meta.json", edges_meta)):
        p = os.path.join(OUT, name)
        with open(p, "w") as f:
            json.dump(obj, f, separators=(",", ":"))
        print(f"wrote {name:24s} {os.path.getsize(p)/1048576:7.2f} MB")


if __name__ == "__main__":
    main()

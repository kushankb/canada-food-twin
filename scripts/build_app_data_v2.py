"""
build_app_data_v2.py — Canada food twin, directional + food-group app payload.

Turns the Canada extraction into the app's shipped payload (static/data/). Decisions worth
knowing before changing anything here:

  1. FULL network. No calorie threshold: every Canada-linked edge ships, packed into a
     binary (`edges.bin`, ~41 bytes/edge) rather than JSON. See PACK LAYOUT in pack_edges().
  2. FOOD GROUPS. `data/food_groups.csv` maps all 82 FBS commodities onto 12 groups; every
     aggregate is cut by group as well as in total.
  3. NAME NORMALISATION. The source writes some commodities two ways ("Aquatic Animals,
     Others" / "Aquatic Animals  Others"). `norm_commodity` folds them back together.
  4. CONNECTORS. Edges with an admin-region centroid at one end (CAN.8_1-road2201886_CAN,
     port1132-PER.17_1) are tagged scope=connector. Their tonnage is real but their geometry
     is a straight line to a centroid, not a route, so the map hides them.
  5. ROUTE MIX, NOT MODE MIX. Land/sea and direct/re-export shares come from the O-D table's
     flow_type, i.e. one count per journey. Summing edge tonnage by mode would count a truck
     trip once per road segment (hundreds) and a sea leg a handful of times.
  6. PARTNERS PER EDGE. When the per-edge parts carry a `partner` column (extraction run with
     the partner-keyed accumulator, tag allp), each edge gets its partner mix and each partner
     gets its own edge list (pe/<direction>/<partner>.bin), fetched when a country is
     selected. Without that column the app still works; it just cannot trace a partner's
     routes.

Inputs (data/):
    canada_od_<tag>.csv                 origin->destination trade, per commodity
    canada_edges_<tag>.csv              per-edge throughput
    _parts_<parts-tag>/edges_*.parquet  per-edge, per-commodity (and per-partner) detail
    canada_edge_geometry_<tag>.csv      edge_id -> endpoints
    food_groups.csv                     commodity -> food group
    --places-src district_stats.json    country/province names and label points

Outputs (static/data/):
    meta.json            coverage, units, caveats, headline totals by direction
    partners.json        partner concentration: overall, by food group, by commodity
    commodities.json     per-commodity dependence, tagged with its food group
    foodgroups.json      per-group concentration, partners, provinces, route mix
    provinces.json       per-province trade, by group, with partners and commodities
    choropleth.json      tonnage by partner country and by province, per direction and group
    partner_detail.json  per partner: groups, commodities, provinces, route mix, dependence
    places.json          names and label points for search and panels
    edges.bin            packed edge geometry + quantities + food-group mix
    edges_meta.json      the key to edges.bin: offsets, dtypes, code tables
    ec/<shard>.json      edge index -> commodities and partners carried, sharded 256 ways
    pe/<dir>/<code>.bin  partner -> every edge its trade uses (uint32 index, float32 tonnes)

Run: python3 scripts/build_app_data_v2.py --tag all [--parts-tag allp]
"""

import argparse
import glob
import json
import os
import re
import shutil
from collections import defaultdict

import numpy as np
import pandas as pd

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(BASE, "data")
OUT = os.path.join(BASE, "static", "data")
DEFAULT_PLACES = os.path.expanduser(
    "~/Desktop/FoodTransportInfrastructure/static/district_stats.json")

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
# Wire format for edges.bin `scope`. Append only: existing codes must keep their index.
SCOPES = ["canada", "maritime_port", "other", "connector"]
# The source's four international route datasets. Domestic ("within") has its own.
ROUTE_TYPES = ["land_dom", "land_re", "sea_dom", "sea_re"]
# Shard count for the per-edge detail. 256 keeps each file ~55 KB.
EC_SHARDS = 256
# An endpoint like CAN.8_1 or PER.17_1 is an admin-region centroid, not a network node.
ADMIN_ENDPOINT = r"(?:^|-)[A-Z]{3}\.\d+_\d+(?:-|$)"


def norm_commodity(s):
    """Fold the source's double-space variants back onto their comma spelling."""
    return re.sub(r"\s{2,}", ", ", str(s)).strip()


def norm_partner(code):
    """A few territories arrive as dotless admin codes (ABW_1_1, MLT_1_1); their country is
    the first three letters. Canadian province codes (CAN.9_1) are left alone."""
    code = str(code)
    return code[:3] if re.fullmatch(r"[A-Z]{3}_\d+_\d+", code) else code


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


def route_mix(df):
    """Share of tonnage by route type — land vs sea, direct vs re-export — one count per
    journey. None for domestic flows, which have no international route type."""
    s = df.groupby("flow_type").tonnes.sum().reindex(ROUTE_TYPES).fillna(0.0)
    tot = float(s.sum())
    if tot <= 0:
        return None
    return {k: round(float(v) / tot, 4) for k, v in s.items()}


def round_map(series):
    s = series[series > 0]
    return {str(k): round(float(v), 1) for k, v in s.items()}


def load_inputs(tag, parts_tag):
    xw = pd.read_csv(os.path.join(DATA, "food_groups.csv"))
    fg_of = dict(zip(xw.commodity, xw.food_group))

    od = pd.read_csv(os.path.join(DATA, f"canada_od_{tag}.csv"))
    for c in ("from_iso3", "to_iso3"):
        od[c] = od[c].map(norm_partner)
    od["commodity"] = od.commodity.map(norm_commodity)
    od["food_group"] = od.commodity.map(fg_of).fillna("Other")
    # The Canadian end of the journey: where the food lands, or where it left from.
    od["ca_admin"] = np.where(od.direction == "import", od.to_admin, od.from_admin)
    od["partner"] = np.where(od.direction == "import", od.from_iso3, od.to_iso3)

    edges = pd.read_csv(os.path.join(DATA, f"canada_edges_{tag}.csv"))
    is_conn = edges.edge_id.str.contains(ADMIN_ENDPOINT, regex=True)
    edges.loc[is_conn, "scope"] = "connector"

    geo_path = os.path.join(DATA, f"canada_edge_geometry_{tag}.csv")
    geo = pd.read_csv(geo_path) if os.path.exists(geo_path) else pd.DataFrame()

    parts = sorted(glob.glob(os.path.join(DATA, f"_parts_{parts_tag}", "edges_[0-9]*.parquet")))
    frames, pframes = [], []
    for p in parts:
        df = pd.read_parquet(p)
        # Per-partner detail multiplies rows by the number of partners on each edge. Fold it
        # out file by file (each file is one commodity) so memory stays flat.
        if "partner" in df.columns:
            pframes.append(df.groupby(["edge_id", "direction", "partner"],
                                      as_index=False).tonnes.sum())
            df = df.groupby(["edge_id", "direction", "commodity", "scope", "mode"],
                            as_index=False).tonnes.sum()
        frames.append(df)
    ec = pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()
    ep = pd.concat(pframes, ignore_index=True) if pframes else pd.DataFrame()
    if not ep.empty:
        ep["partner"] = ep.partner.map(norm_partner)
        ep = ep.groupby(["edge_id", "direction", "partner"], as_index=False).tonnes.sum()
    if not ec.empty:
        ec["commodity"] = ec.commodity.map(norm_commodity)
        ec["food_group"] = ec.commodity.map(fg_of).fillna("Other")

    print(f"O-D {len(od):,} rows | edges {len(edges):,} ({int(is_conn.sum())} connectors) | "
          f"geometry {len(geo):,} | per-commodity {len(ec):,} | per-partner {len(ep):,} "
          f"from {len(parts)} parts ({parts_tag})")
    return od, edges, geo, ec, ep


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


def build_foodgroups(od, partners):
    """Per-group totals, concentration, province mix and route mix."""
    out = {}
    for d in DIRECTIONS:
        sub = od[od.direction == d]
        if sub.empty:
            continue
        tot_t = float(sub.tonnes.sum()) or 1.0
        tot_k = float(np.nansum(sub.kcal)) or 1.0
        rows = []
        for g, gg in sub.groupby("food_group"):
            b = (partners.get(d, {}).get("by_food_group", {}) or {}).get(g) or {}
            k = float(np.nansum(gg.kcal))
            rows.append({
                "food_group": g,
                "tonnes": round(float(gg.tonnes.sum()), 1),
                "kcal": k,
                "tonne_share": round(float(gg.tonnes.sum()) / tot_t, 4),
                "calorie_share": round(k / tot_k, 4),
                "n_commodities": int(gg.commodity.nunique()),
                "n_partners": b.get("n_partners"),
                "hhi": b.get("hhi"),
                "effective_partners": b.get("effective_partners"),
                "top_partner": (b.get("top1") or {}).get("iso3"),
                "top_partner_share": (b.get("top1") or {}).get("share"),
                "partners_for_90pct": b.get("partners_for_90pct"),
                "top_partners": b.get("top_partners", [])[:10],
                "provinces": share_list(gg.groupby("ca_admin").tonnes.sum(), 13, key="admin"),
                "commodities": share_list(gg.groupby("commodity").tonnes.sum(), 10, key="commodity"),
                "routes": route_mix(gg),
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
            conc = concentration(gg.groupby("partner").tonnes.sum(), top_n=10) or {}
            rows.append({
                "admin": admin, "name": name, "code": code,
                "tonnes": round(float(gg.tonnes.sum()), 1),
                "kcal": float(np.nansum(gg.kcal)),
                "share_of_national": round(float(gg.tonnes.sum()) / tot_t, 4),
                "n_partners": conc.get("n_partners"),
                "hhi": conc.get("hhi"),
                "effective_partners": conc.get("effective_partners"),
                "top_partner": (conc.get("top1") or {}).get("iso3"),
                "top_partner_share": (conc.get("top1") or {}).get("share"),
                "top_partners": conc.get("top_partners", []),
                "food_groups": share_list(gg.groupby("food_group").tonnes.sum(), 12, key="food_group"),
                "commodities": share_list(gg.groupby("commodity").tonnes.sum(), 10, key="commodity"),
                "routes": route_mix(gg),
            })
        rows.sort(key=lambda r: -r["tonnes"])
        out[d] = rows
    return out


def build_choropleth(od):
    """Tonnage by partner country and by province, per direction, overall and per group."""
    out = {"partners": {}, "provinces": {}}
    for d in DIRECTIONS:
        sub = od[od.direction == d]
        if sub.empty:
            continue
        for key, col in (("partners", "partner"), ("provinces", "ca_admin")):
            if key == "partners" and d == "within":
                continue  # every domestic partner is Canada itself
            block = {"ALL": round_map(sub.groupby(col).tonnes.sum())}
            for g, gg in sub.groupby("food_group"):
                block[g] = round_map(gg.groupby(col).tonnes.sum())
            out[key][d] = block
    return out


def build_partner_detail(od):
    """Everything the country panel shows for one partner, per direction."""
    out = {}
    for d in ("import", "export"):
        sub = od[od.direction == d]
        if sub.empty:
            continue
        tot = float(sub.tonnes.sum()) or 1.0
        group_tot = sub.groupby("food_group").tonnes.sum()
        order = sub.groupby("partner").tonnes.sum().sort_values(ascending=False)
        rank = {k: i + 1 for i, k in enumerate(order.index)}
        block = {}
        for iso, gg in sub.groupby("partner"):
            t = float(gg.tonnes.sum())
            by_g = gg.groupby("food_group").tonnes.sum()
            dep = (by_g / group_tot.reindex(by_g.index)).sort_values(ascending=False)
            block[str(iso)] = {
                "rank": rank[iso], "of": int(len(order)),
                "tonnes": round(t, 1),
                "kcal": float(np.nansum(gg.kcal)),
                "share": round(t / tot, 4),
                "food_groups": share_list(by_g, 12, key="food_group"),
                "commodities": share_list(gg.groupby("commodity").tonnes.sum(), 8, key="commodity"),
                "provinces": share_list(gg.groupby("ca_admin").tonnes.sum(), 13, key="admin"),
                "routes": route_mix(gg),
                # This partner's share of Canada's national tonnage in each group — the
                # dependence reading, as opposed to food_groups, which is its own mix.
                "dependence": [{"food_group": str(k), "share": round(float(v), 4)}
                               for k, v in dep.items() if v >= 0.005],
            }
        out[d] = block
    return out


def build_places(src, od):
    """Names and label points for every partner country and Canadian province."""
    wanted = set(od.from_iso3.dropna()) | set(od.to_iso3.dropna())
    countries, provinces = {}, {}
    if src and os.path.exists(src):
        with open(src) as f:
            d = json.load(f)
        for iso, c in (d.get("countries") or {}).items():
            if iso in wanted:
                countries[iso] = {"name": c.get("name") or iso,
                                  "lat": c.get("lat"), "lon": c.get("lon")}
        for adm, c in (d.get("districts") or {}).items():
            if adm in PROVINCES:
                provinces[adm] = {"name": PROVINCES[adm][0], "code": PROVINCES[adm][1],
                                  "lat": c.get("lat"), "lon": c.get("lon")}
    else:
        print(f"WARNING: {src} not found — places.json will carry codes, not names")
    missing = sorted(wanted - set(countries))
    for iso in missing:
        countries[iso] = {"name": iso, "lat": None, "lon": None}
    for adm, (name, code) in PROVINCES.items():
        provinces.setdefault(adm, {"name": name, "code": code, "lat": None, "lon": None})
    if missing:
        print(f"places: {len(missing)} partner codes have no name/label point: {missing[:12]}")
    return {"countries": countries, "provinces": provinces}


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
            fg = np.nan_to_num(acc / np.where(tot > 0, tot, np.nan) * 255).round().astype(np.uint8)

        ecc = ec.groupby(["edge_id", "direction", "commodity"], as_index=False).tonnes.sum()
        top = ecc.sort_values("tonnes", ascending=False).drop_duplicates(["edge_id", "direction"])
        commodity_codes = sorted(ec.commodity.unique())
        cidx = {c: i for i, c in enumerate(commodity_codes)}
        for r in top.itertuples(index=False):
            i = pos.get((r.edge_id, r.direction))
            if i is not None:
                topc[i] = cidx.get(r.commodity, 0)

    dir_c = e.direction.map({d: i for i, d in enumerate(DIRECTIONS)}).fillna(0).astype(np.uint8)
    mode_c = e["mode"].map({m: i for i, m in enumerate(MODES)}).fillna(len(MODES) - 1).astype(np.uint8)
    scope_c = e.scope.map({s: i for i, s in enumerate(SCOPES)}).fillna(SCOPES.index("other")).astype(np.uint8)

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


def ranked(df, key, n):
    """Top-n rows per (edge, direction) as shares of that edge's FULL tonnage — not of the
    top-n subtotal, which would overstate every share."""
    df = df.sort_values(["edge_id", "direction", "tonnes"], ascending=[True, True, False]).copy()
    grp = df.groupby(["edge_id", "direction"], sort=False)
    df["tot"] = grp.tonnes.transform("sum")
    df["r"] = grp.cumcount()
    df = df[df.r < n]
    out = defaultdict(list)
    for eid, d, k, t, tot in zip(df.edge_id, df.direction, df[key], df.tonnes, df.tot):
        out[(eid, d)].append({"k": str(k), "s": round(float(t / tot), 3) if tot > 0 else 0.0})
    return out


def write_edge_detail(ec, ep, pos):
    """ec/<index % EC_SHARDS>.json -> {index: {c: [commodity shares], p: [partner shares]}}."""
    com = ranked(ec.groupby(["edge_id", "direction", "commodity"], as_index=False).tonnes.sum(),
                 "commodity", 6) if not ec.empty else {}
    par = ranked(ep, "partner", 6) if not ep.empty else {}
    shards = [{} for _ in range(EC_SHARDS)]
    for key, i in pos.items():
        c, p = com.get(key), par.get(key)
        if c or p:
            shards[i % EC_SHARDS][str(i)] = {"c": c or [], "p": p or []}
    root = os.path.join(OUT, "ec")
    shutil.rmtree(root, ignore_errors=True)
    os.makedirs(root)
    for i, sh in enumerate(shards):
        with open(os.path.join(root, f"{i}.json"), "w") as f:
            json.dump(sh, f, separators=(",", ":"))
    size = sum(os.path.getsize(os.path.join(root, f"{i}.json")) for i in range(EC_SHARDS))
    print(f"wrote ec/ {EC_SHARDS} shards       {size/1048576:7.2f} MB total, "
          f"{size/EC_SHARDS/1024:.0f} KB each")


def write_partner_edges(ep, pos):
    """pe/<direction>/<partner>.bin — every edge a partner's trade uses, heaviest first.
    Layout: uint32[n] edge index into edges.bin, then float32[n] tonnes for that partner.
    Fetched only when that country (or, for domestic, that province) is selected."""
    root = os.path.join(OUT, "pe")
    shutil.rmtree(root, ignore_errors=True)
    if ep.empty:
        print("pe/ skipped — per-edge parts carry no partner column (rerun extraction, tag allp)")
        return {}
    idx = np.fromiter((pos.get((e, d), -1) for e, d in zip(ep.edge_id, ep.direction)),
                      dtype=np.int64, count=len(ep))
    ep = ep.assign(idx=idx)
    ep = ep[ep.idx >= 0]
    index, size = {}, 0
    for (d, partner), g in ep.groupby(["direction", "partner"]):
        g = g.sort_values("tonnes", ascending=False)
        os.makedirs(os.path.join(root, d), exist_ok=True)
        path = os.path.join(root, d, f"{partner}.bin")
        with open(path, "wb") as f:
            f.write(g.idx.to_numpy(np.uint32).tobytes())
            f.write(g.tonnes.to_numpy(np.float32).tobytes())
        size += os.path.getsize(path)
        index.setdefault(d, {})[str(partner)] = int(len(g))
    n = sum(len(v) for v in index.values())
    print(f"wrote pe/ {n} partner files    {size/1048576:7.2f} MB total")
    return index


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--tag", default="all")
    ap.add_argument("--parts-tag", default=None,
                    help="Read per-edge parts from _parts_<parts-tag> (default: --tag).")
    ap.add_argument("--places-src", default=DEFAULT_PLACES,
                    help="district_stats.json carrying country/province names and label points.")
    args = ap.parse_args()
    os.makedirs(OUT, exist_ok=True)

    od, edges, geo, ec, ep = load_inputs(args.tag, args.parts_tag or args.tag)
    kcal_per_t = energy_per_tonne(od)

    partners = build_partners(od)
    commodities = build_commodities(partners)
    foodgroups = build_foodgroups(od, partners)
    provinces = build_provinces(od)
    choropleth = build_choropleth(od)
    partner_detail = build_partner_detail(od)
    places = build_places(args.places_src, od)

    buf, edges_meta, kept = pack_edges(edges, geo, ec, kcal_per_t)
    with open(os.path.join(OUT, "edges.bin"), "wb") as f:
        f.write(buf)
    n_conn = int((kept.scope == "connector").sum())
    print(f"packed {edges_meta['count']:,} edges "
          f"({edges_meta['byteLength']/1048576:.2f} MB, "
          f"{edges_meta['byteLength']/max(edges_meta['count'],1):.0f} bytes/edge); "
          f"{n_conn} connectors tagged; dropped {edges_meta['dropped_no_geometry']:,} without geometry")

    pos = {(r.edge_id, r.direction): i for i, r in enumerate(kept.itertuples(index=False))}
    write_edge_detail(ec, ep, pos)
    edges_meta["ecShards"] = EC_SHARDS
    edges_meta["partnerEdges"] = write_partner_edges(ep, pos)

    meta = {
        "country": "CAN",
        "tag": args.tag,
        "partsTag": args.parts_tag or args.tag,
        "coverage": "full network — no calorie threshold applied",
        "units": {"tonnes": "metric tonnes", "kcal": "kilocalories"},
        "foodGroups": FOOD_GROUPS,
        "routeTypes": ROUTE_TYPES,
        "provinces": [{"admin": k, "name": v[0], "code": v[1]} for k, v in PROVINCES.items()],
        "hasPartnerEdges": bool(edges_meta["partnerEdges"]),
        "headline": {
            d: {"tonnes": round(float(od[od.direction == d].tonnes.sum()), 1),
                "kcal": float(np.nansum(od[od.direction == d].kcal)),
                "commodities": int(od[od.direction == d].commodity.nunique()),
                "food_groups": int(od[od.direction == d].food_group.nunique()),
                "partners": int(od[od.direction == d].partner.nunique()),
                "provinces": int(od[od.direction == d].ca_admin.isin(list(PROVINCES)).pipe(
                    lambda m: od[od.direction == d].ca_admin[m].nunique())),
                "hhi": (partners.get(d, {}).get("overall") or {}).get("hhi"),
                "effective_partners": (partners.get(d, {}).get("overall") or {}).get("effective_partners"),
                "top_partner": ((partners.get(d, {}).get("overall") or {}).get("top1") or {}).get("iso3"),
                "top_partner_share": ((partners.get(d, {}).get("overall") or {}).get("top1") or {}).get("share"),
                "routes": route_mix(od[od.direction == d])}
            for d in DIRECTIONS if (od.direction == d).any()
        },
        "caveats": [
            "Per-edge quantities are directional throughput for Canada-linked journeys only, "
            "derived from origin->destination routes -- not the undirected global totals used "
            "by the global app, and not subject to its ~46x destination multi-counting.",
            "Edge scope is Canadian territory plus maritime and port legs. Inland delivery "
            "inside partner countries is deliberately excluded: we do not model foreign road "
            "criticality.",
            "Connector edges -- straight links from a network node to a region's centroid -- "
            "carry real tonnage but no real path, so the map does not draw them.",
            "Long sea and port legs, and a handful of long rail links, are drawn as straight lines "
            "between network nodes, so some -- notably the Great Lakes and St. Lawrence legs -- cross "
            "land on the map. The geometry is schematic; the tonnage on each leg is not.",
            "Criticality here is throughput share, not a no-alternative-route counterfactual. "
            "A high-throughput edge is not automatically irreplaceable.",
            "Concentration (HHI, effective partners) is measured on tonnage by partner "
            "country, so it describes sourcing breadth, not substitutability: two suppliers "
            "in one climate zone count as two.",
            "Land/sea and direct/re-export shares count each journey once, from the source's "
            "route datasets. They describe how journeys are routed, not the mode of every "
            "segment along the way.",
            "Within-Canada domestic distribution is sparse in the source "
            "(Data_WithinCountry covers surplus->deficit redistribution only).",
            "Route-level totals fall ~10% below O-D totals: some flows have no routable path.",
            "Provinces are the Canadian end of each journey -- destination for imports, origin "
            "for exports -- not the province of final consumption or of primary production.",
        ],
    }

    for name, obj in (("meta.json", meta), ("partners.json", partners),
                      ("commodities.json", commodities), ("foodgroups.json", foodgroups),
                      ("provinces.json", provinces), ("choropleth.json", choropleth),
                      ("partner_detail.json", partner_detail), ("places.json", places),
                      ("edges_meta.json", edges_meta)):
        p = os.path.join(OUT, name)
        with open(p, "w") as f:
            json.dump(obj, f, separators=(",", ":"))
        print(f"wrote {name:24s} {os.path.getsize(p)/1048576:7.2f} MB")


if __name__ == "__main__":
    main()

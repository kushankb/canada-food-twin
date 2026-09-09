# Project brief — Canada Food Twin

## The one question

**Where does Canada's food come from, where does it go, and how exposed is that pattern?**

A visitor should be able to answer, within 30 seconds of landing: Canada buys its food from
very few countries and sells it to many. Everything else in the app is a second click.

## Why this app exists separately from the global one

`globalfoodsupply.kushankbajaj.com` ships **undirected** throughput: a single edge aggregates
domestic, international, transit and re-export journeys into one number, and its country
ranking multi-counts the same food roughly 46 times. It can rank connectivity; it cannot say
"import" or "export".

The directional structure was in the source parquets all along and was collapsed when the
global JSON was built. This app un-collapses it for one country. Per-edge quantities here are
directional, single-counted, and joined to origin→destination admin-1 pairs — so import and
export are real categories, not labels applied to an aggregate.

## Data contract

| Stage | Location | Size |
|---|---|---|
| Source flows | `Output/Version8/PostProcessed/*/Tonnage/foodgroup1/Flows_*.csv.gz` | 413 files, 47.7 M rows scanned |
| Canada extraction | `scripts/extract_canada_flows.py` → `data/canada_od_all.csv`, `canada_edges_all.csv`, `_parts_all/*.parquet` | 18 MB O-D, 3.1 M per-commodity edge rows |
| Geometry | `scripts/attach_geometry.py` → `data/canada_edge_geometry_all.csv` | 58,220 unique edges, 100% resolved |
| Food groups | `data/food_groups.csv` (hand-built, 82/82 commodities covered) | 12 groups |
| Build | `scripts/build_app_data_v2.py` | — |
| Shipped | `public/data/` | **3.0 MB initial**, 55 KB per edge click |

Shipped payload: `edges.bin` 2.74 MB (70,198 edges at 41 bytes each), `partners.json` 180 KB,
`foodgroups.json` 58 KB, `provinces.json` 58 KB, `commodities.json` 40 KB, `meta.json` 2.7 KB,
plus `ec/0–255.json` fetched on demand.

Two source problems are fixed in `build_app_data_v2.py`, not upstream:

1. **Commodity name variants.** The source writes some names twice — `Aquatic Animals, Others`
   and `Aquatic Animals  Others`. Left alone, one commodity becomes two and its HHI is wrong.
   14 variants, 0.49% of tonnage. `norm_commodity()` folds them back.
2. **No calorie threshold.** The earlier build kept 99% of calories (36,496 of 70,198 edges).
   The full network now ships, because the binary encoding makes it cheaper than the old
   truncated JSON was.

## Views

| View | The one question it answers |
|---|---|
| Network | Which infrastructure carries Canada's food, and where does it run? |
| Concentration | How many countries does Canada actually depend on? |
| Food groups | Does the answer change by what kind of food it is? |
| Provinces | Which provinces carry the trade, and in what? |
| Exposure *(phase 2)* | Where does concentration meet climate and hazard risk? |

The **direction toggle governs all of them**. Import / Export / Domestic is the app's primary
axis, not a filter inside one chart.

## What the data actually says

| | Imports | Exports |
|---|---|---|
| Tonnage | 21.7 Mt | 65.5 Mt |
| Calories | 38.7 trillion kcal | 209.4 trillion kcal |
| Partners | 145 | 175 |
| HHI | 0.560 | 0.079 |
| **Effective partners** | **1.79** | **12.69** |

The asymmetry is the story. Canada exports to the world and buys from its neighbour: the USA
supplies 74.6% of imported tonnage, 87% of imported oilseed calories and 84% of imported grain
calories. The one export dependency that mirrors it is Starchy Roots — potatoes — at HHI 0.865
with 93% going to the USA.

## Uncertainty & provenance

There are **no uncertainty bands in this dataset** — it is a routed allocation, not an
ensemble — so the honesty burden falls on scope statements instead. Every headline number
carries direction, units and coverage. The specific things that must never be implied:

- Concentration is measured on **partner countries by tonnage**, so it describes sourcing
  breadth, not substitutability. Two suppliers in one climate zone count as two.
- `exposure_index` (calorie share × HHI) is a **ranking device**, not a probability, forecast
  or impact estimate.
- Edge throughput is **not** spare capacity, and a high-throughput edge is **not**
  automatically irreplaceable — there is no no-alternative-route counterfactual here.
- Provinces are the **Canadian end of the journey** (destination for imports, origin for
  exports), not final consumption or primary production.
- Domestic flows are **sparse by construction**: the source models surplus-to-deficit
  redistribution only.
- Route totals fall ~10% below O-D totals; some flows have no routable path.

Internal key → display label mappings live in `src/config/index.ts`. Every entry has a `desc`
string, and those strings are the only glossary the UI is allowed to use.

## Non-goals

- **No import/export "balance" or self-sufficiency ratio.** Tonnage in and tonnage out are
  different commodity mixes; differencing them would invent a number the data cannot support.
- **No causal claims.** Exposure overlaps are associations, never "X will cause Y".
- **No foreign inland infrastructure.** Edge scope is Canadian territory plus maritime and
  port legs. Modelling road criticality inside partner countries is out of scope.
- **No time series.** The source is a single allocation, not a panel.
- **No backend.** Static site, all computation done at build time in Python.

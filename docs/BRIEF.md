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
| Partner-keyed parts | `extract_canada_flows.py --tag allp` → `_parts_allp/` | 2.87 M edge × partner rows |
| Shipped | `static/data/` | **~3.6 MB initial**; ~86 KB per segment click; ≤134 KB per country selected |

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

## Layout and views

Map-first, on globalfoodsupply's layout. The **direction toggle governs everything**: Import /
Export / Domestic is the app's primary axis, not a filter inside one chart.

| Element | The one question it answers |
|---|---|
| Transport routes (layer) | Which infrastructure carries Canada's food, and where does it run? |
| Partner countries (layer) | Where does it come from, or go to — and how much from each? |
| Provinces (layer) | Where does it enter or leave Canada? |
| Canada overview (right panel) | How many countries does Canada actually depend on, and does that change by food group? |
| Country panel (click a country) | What does Canada trade with this country, and which routes does that trade use? |
| Province panel (click a province) | What enters or leaves through here, and from whom? |
| Segment popup (click a line) | What does this segment carry, for whom, and what share of the trade passes here? |
| Exposure *(phase 2)* | Where does concentration meet climate and hazard risk? |

Why SvelteKit: the first scaffold was a React dashboard with tabs. Once the target became "like
globalfoodsupply", both house rules — clone the reference's structure; map-centred apps use
SvelteKit — pointed the same way, and only the shell existed, so it moved before any view was
built.

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
- **Import provinces are a demand allocation.** The source splits national imports across
  provinces by population weight (`weight_pop` in `Demand_subnational.csv`; r = 0.999 with the
  2021 census), so every province has the
  national partner and food-group mix. The build measures this and the UI hides the copied
  breakdowns; the import province layer is labelled a demand map, not ports of entry. **Export
  provinces are real** — they come from production allocation and differ by province.
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

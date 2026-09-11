# Canada Food Twin

**Where Canada's food comes from, where it goes, and the infrastructure that moves it.**

→ https://canadafoodsupply.kushankbajaj.com

An interactive map of Canada's food trade at the level of individual transport segments:
70,198 road, rail, maritime and port edges carrying 82 commodities between Canada and 175
partner countries, cut by direction, food group and province. Built on the same layout as the
global map — switch between imports and exports, click a country to see what Canada trades with
it and trace the routes that trade uses, click a line to see what it carries and for whom.

Companion to [globalfoodsupply.kushankbajaj.com](https://globalfoodsupply.kushankbajaj.com),
which covers the whole world but cannot distinguish imports from exports. This one can — see
[Why directional](#why-directional).

## The headline

|  | Imports | Exports |
|---|---|---|
| Tonnage | 21.7 Mt | 65.5 Mt |
| Calories | 38.7 trillion kcal | 209.4 trillion kcal |
| Partner countries | 145 | 175 |
| HHI | 0.560 | 0.079 |
| **Effective partners** | **1.79** | **12.69** |

Canada sells food to the world and buys it from its neighbour. The United States supplies
74.6% of imported tonnage, 87% of imported oilseed calories and 84% of imported grain
calories. Despite 145 countries appearing in the import data, the concentration is that of
fewer than two equally-sized suppliers.

The mirror image on the export side is narrow but real: **Starchy Roots** — potatoes — runs at
HHI 0.865 with 93% going to the United States.

## Why directional

The global app ships *undirected* throughput. One edge there aggregates domestic,
international, transit and re-export journeys into a single number, and its country ranking
adds each edge's full energy to every destination it serves — multi-counting the same food
about 46 times. It ranks connectivity; it cannot say "import" or "export".

That directional structure existed in the source parquets and was collapsed when the global
JSON was built. This app un-collapses it for one country. Quantities here are directional,
single-counted, and tied to origin→destination admin-1 pairs.

## Data

| Stage | Output | Size |
|---|---|---|
| Source | `Output/Version8/PostProcessed/…/Flows_*.csv.gz` | 413 files, 47.7 M rows |
| Extract | `data/canada_od_all.csv`, `canada_edges_all.csv`, `_parts_all/` | 3.1 M per-commodity edge rows |
| Build | `static/data/` | **~3.6 MB initial load** |

The network ships as a packed binary — `edges.bin`, 41 bytes per edge — rather than JSON,
which is what makes the full 70,198-edge network affordable instead of a truncated subset.
Two things load only on demand: a clicked segment's commodity and partner mix (`ec/`, 256
shards of ~86 KB) and a selected country's own segments (`pe/`, one file per partner, the
largest ~134 KB).

The extraction keys every segment by partner as well as commodity, so a segment can say whose
trade it carries (the Windsor–Detroit rail crossing: 95% US, 5% Mexico) and a country can be
traced across the network.

Food groups come from `data/food_groups.csv`, a hand-built crosswalk covering all 82 FAO Food
Balance Sheet commodities across 12 groups.

## Reading the numbers honestly

- **Concentration is sourcing breadth, not substitutability.** HHI counts partner countries
  by tonnage; two suppliers in one climate zone count as two.
- **`exposure_index` (calorie share × HHI) ranks, it does not predict.** Not a probability, a
  forecast or an impact estimate.
- **Edge throughput is not capacity or criticality.** No alternative-route counterfactual is
  modelled, so a busy edge is not automatically irreplaceable.
- **Import provinces are modelled, export provinces are not.** The source splits Canada's
  imports across provinces in proportion to each province's share of population (the source's
  `weight_pop`; r = 0.999 against the 2021 census), so every province shows the same partner mix — the US at
  74.6%, everywhere. The import province layer is a demand map, not ports of entry, and the app
  says so. Export origins come from production and genuinely differ: Saskatchewan ships 40% of
  exports, with China as its largest buyer.
- **Domestic flows are sparse by construction**; the source models surplus-to-deficit
  redistribution only, so they are not comparable in magnitude to imports or exports.
- **No balance or self-sufficiency figures**, deliberately: imports and exports are different
  commodity mixes and differencing them would invent a number the data cannot support.
- **Long sea and port legs are schematic straight lines**, so some — notably the Great Lakes
  and St. Lawrence legs — cross land on the map. The global map has the same geometry.
- **For re-export flows the partner shown is the re-exporter**, not where the food was grown.
- Route totals fall ~10% below origin–destination totals — some flows have no routable path.

## Development

```bash
npm install
cp .env.example .env        # add a Mapbox public token as PUBLIC_MAPBOX_TOKEN
npm run dev
```

Rebuilding the payload needs the analysis outputs under `Output/Version8/` and Python with
pandas, numpy and pyarrow:

```bash
python3 scripts/build_app_data_v2.py --tag all --parts-tag allp
```

The deployed site needs the repository secret `PUBLIC_MAPBOX_TOKEN` and a DNS `CNAME` record
`canadafoodsupply` → `kushankb.github.io`.

```bash
python3 scripts/check_palette.py
```

`check_palette.py` guards the food-group palette's perceptual separation and must pass before
any colour change ships.

## Stack

SvelteKit 2 · Svelte 5 · TypeScript · Mapbox GL + deck.gl · Tailwind 4 + daisyUI. Static site,
no backend; every aggregate is precomputed in Python at build time. Layout, map chrome and
boundary tilesets are shared with the global map.

## Documentation

- `docs/BRIEF.md` — the one question, data contract, views, non-goals
- `CLAUDE.md` — repo conventions and the data-semantics rules

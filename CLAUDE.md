# CLAUDE.md — Canada Food Twin

Static React app: where Canada's food comes from, where it goes, and the infrastructure that
moves it. Deployed to https://canadafoodsupply.kushankbajaj.com via GitHub Pages.

Read `docs/BRIEF.md` first — it holds the one question, the data contract, the view list and
the non-goals. This file covers how to work in the repo.

## Commands

```bash
npm run dev                                  # vite dev server
npm run build                                # tsc -b && vite build -> dist/
npm run lint
python3 scripts/build_app_data_v2.py --tag all   # rebuild public/data/ (~3 min)
python3 scripts/check_palette.py                 # must PASS before palette changes ship
```

## Architecture

Static site. No backend, no runtime computation Python could do once at build time.

```
scripts/          Python. Build-time only.
  extract_canada_flows.py   source parquets -> data/canada_*.csv  (slow, ~16 min)
  attach_geometry.py        edge_id -> endpoint coordinates
  build_app_data_v2.py      data/ -> public/data/                 (the one to rerun)
  check_palette.py          OKLab separation guard for the food-group palette
data/             Intermediate artefacts. Gitignored except food_groups.csv.
public/data/      The shipped payload. Committed.
src/config/       Every label, colour, unit, code and definition. Read this first.
src/utils/        Formatters. No number is formatted anywhere else.
src/hooks/        useData — one fetch, module-level cache.
src/types/        Shapes of public/data/*. Mirrors build_app_data_v2.py.
```

## Rules specific to this repo

**Direction is the primary axis.** `import | export | within` is app-level state that every
view re-reads. It is never a per-chart filter, and switching it never refetches.

**`edges.bin` and `edges_meta.json` are one unit.** The binary layout is defined in
`pack_edges()` in `build_app_data_v2.py` and decoded in `loadNetwork()` in
`src/hooks/useData.ts`. Change one, change the other, and rerun the build — the loader
throws on a byte-length mismatch rather than silently misreading. `codes.foodGroup` order is
the wire format for the `fg` section; never reorder it without rebuilding.

**Per-edge commodity detail is sharded.** `ec/<index % 256>.json`, fetched on click. Do not
load it eagerly; whole, it is five times the size of the network.

**Palette changes must pass `check_palette.py`.** Four food-group colours deliberately differ
from the house set — two new (Sugar and Sweeteners, Stimulants and Spices), two re-separated
(Fruits, Pulses). The reasoning is in the header of `src/config/palette.ts`.

## Data semantics — do not violate these

This app's data is **directional and single-counted**, unlike the global app's. The ~46x
multi-counting caveat that governs `globalfoodsupply` does **not** apply here, and neither
does its ban on the words "import" and "export". What does apply:

1. **Concentration is sourcing breadth, not substitutability.** HHI and effective partners
   are computed on partner countries by tonnage. Two suppliers sharing a climate zone count
   as two independent partners. Never present a low HHI as resilience.
2. **`exposure_index` is a ranking device.** Calorie share × HHI. Not a probability, not a
   forecast, not an impact estimate. Say "ranks highest", never "is most likely to fail".
3. **Edge throughput is not capacity or criticality.** A high-throughput edge is not
   automatically irreplaceable; there is no alternative-route counterfactual in this data.
4. **Provinces are the Canadian end of the journey** — destination for imports, origin for
   exports. Not final consumption, not primary production.
5. **Domestic flows are sparse by construction** (surplus-to-deficit redistribution only).
   Never compare their magnitude to imports or exports as if both were complete.
6. **No balance figures.** Imports and exports are different commodity mixes; do not subtract
   them or derive a self-sufficiency ratio.
7. **Route totals fall ~10% below O-D totals** — some flows have no routable path. Network
   view sums will not match headline trade figures, and that is expected.

## Conventions

- Colours, labels, units, codes: `src/config/`. Never inline in a component.
- Numbers: `src/utils/formatters`. Never `toFixed` in a component.
- Data paths: `import.meta.env.BASE_URL`. Never a hard-coded leading `/`.
- Every headline number states its direction, units and coverage.
- Legends are controls: click to isolate, click again to reset, `role="button"` + keyboard.

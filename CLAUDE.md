# CLAUDE.md — Canada Food Twin

Map-first static app: where Canada's food comes from, where it goes, and the routes it takes.
Deployed to https://canadafoodsupply.kushankbajaj.com via GitHub Pages. The Canada companion to
globalfoodsupply.kushankbajaj.com, whose source is `~/Desktop/FoodTransportInfrastructure` —
this app copies its layout, chrome (`src/lib/styles/map.css`), component split and boundary
tilesets, and swaps the payload for directional Canada data.

Read `docs/BRIEF.md` first — the one question, data contract, layers and panels, non-goals.

## Commands

```bash
npm run dev                  # vite dev
npm run build                # static site -> build/
npm run check                # svelte-check (types + a11y)
python3 scripts/check_palette.py          # must PASS before any food-group colour changes

# Rebuild the payload (~3 min). allp = the partner-keyed extraction.
python3 scripts/build_app_data_v2.py --tag all --parts-tag allp

# Re-extract from the V8 route files (~16 min). Only needed if the source changes.
python3 scripts/extract_canada_flows.py --commodity ALL --tag allp
```

## Stack

SvelteKit 2 + Svelte 5 runes (`$state`, `$derived`, `$props`, `{@render}`), adapter-static
with `prerender = true` and `ssr = false` (mapbox-gl and deck.gl need a browser). Mapbox GL v3
basemap + deck.gl `MapboxOverlay` (interleaved). Tailwind 4 + daisyUI 5 (sunset) for the page;
hand-written CSS custom properties for map chrome. TypeScript throughout.

## Layout

```
scripts/                 Python, build-time only
  extract_canada_flows.py    V8 route files -> data/canada_*_<tag>.csv + _parts_<tag>/
  attach_geometry.py         edge_id -> endpoint coordinates
  build_app_data_v2.py       data/ -> static/data/   (the one to rerun)
  check_palette.py           OKLab separation guard for the food-group palette
data/                    Intermediate artefacts. Gitignored except food_groups.csv
static/data/             The shipped payload. Committed.
src/lib/config/          Every label, colour, unit, code, tileset and definition. Read first.
src/lib/data.ts          Loader: one fetch of everything, module-level cache, on-demand shards
src/lib/network.ts       Filters the packed network into deck.gl binary attributes
src/lib/components/      Map, ControlPanel, Legend, SidePanel, DetailPopup, SearchBar, ...
src/routes/+page.svelte  State and wiring
```

## Rules specific to this repo

**Direction is the primary axis.** `import | export | within` is page state that every layer
and panel re-reads. Switching it never refetches.

**`edges.bin` + `edges_meta.json` are one unit.** Layout is defined in `pack_edges()` and decoded
in `loadNetwork()` (`src/lib/data.ts`). Change both together and rebuild; the loader throws on a
byte-length mismatch. `codes.foodGroup` order is the wire format for the `fg` section. `SCOPES`
is append-only (`connector` was added as code 3).

**Two things load on demand, never eagerly.** `ec/<index % 256>.json` (a clicked segment's top
commodities and partners) and `pe/<direction>/<partner>.bin` (every segment a selected
partner's trade uses — uint32 indices then float32 tonnes; largest file ~134 KB).

**The Pacific is folded.** Longitudes east of `MAP.foldLongitude` (100°E) are shifted −360° in
`loadNetwork()`, so trans-Pacific routes run west from BC without breaking at the date line.
Anything that places the camera on a partner (search `flyTo`) must apply the same fold.

**Choropleths go through feature-state.** Partner countries and provinces use the shared
tilesets `kushankb.01l11tz3` (countries, `iso3`) and `kushankb.69o1u9mn` (admin, `ID` = GADM
`CAN.9_1`). Values are set with `setFeatureState({v})`; layers are added once per style load.

**Mapbox token.** `PUBLIC_MAPBOX_TOKEN`, read through `import.meta.env` (`envPrefix` includes
`PUBLIC_`) so a missing token shows a message on the map instead of failing the build. CI
reads it from the repo secret of the same name.

**Palette changes must pass `check_palette.py`.** Four food-group colours deliberately differ
from the house set; the reasoning is in the header of `src/lib/config/palette.ts`.

## Data semantics — do not violate these

This data is **directional and single-counted**, unlike the global app's. The ~46x
multi-counting caveat that governs globalfoodsupply does **not** apply, and neither does its ban
on the words "import" and "export". What does apply:

1. **Concentration is sourcing breadth, not substitutability.** HHI and effective partners are
   computed on partner countries by tonnage. Never present a low HHI as resilience.
2. **`exposure_index` is a ranking device** (calorie share × HHI) — never a probability or forecast.
3. **Segment throughput is not capacity or criticality.** No alternative-route counterfactual exists.
4. **Import provinces are a demand allocation; export provinces are real.** The source splits
   national imports across provinces by population weight (`weight_pop` in
   `Output/Demand_allocated/Demand_subnational.csv`; r = 0.999 with the 2021 census), so every
   province carries the national partner and food-group mix (spread
   0.0015). Export origins come from production allocation and differ by up to 0.26. The build
   measures this (`meta.provinceMix[dir].allocated`) and the UI hides copied breakdowns where it
   holds. Never present an import province as a port of entry.
5. **For re-export flows the partner is the re-exporter**, not where the food was grown.
6. **Route mix, not mode mix.** Land/sea and direct/re-export shares come from O-D `flow_type`,
   one count per journey. Never sum segment tonnage by mode — a truck trip crosses hundreds of
   road segments and would dominate.
7. **Connectors are hidden, not deleted.** `scope = connector` edges (a node to a region
   centroid) carry real tonnage but no real path.
8. **Long sea/port legs and a few rail links are schematic straight lines** and some cross land
   (Great Lakes–St. Lawrence). The global app has the same geometry; there is no better source.
9. **Domestic flows are sparse by construction**; never compare their size to imports or exports.
10. **No balance or self-sufficiency figures.** Imports and exports are different commodity mixes.
11. **Segment totals fall ~10% below O-D totals** — some flows have no routable path.

## Conventions

- Colours, labels, units, codes, tilesets: `src/lib/config/`. Never inline in a component.
- Numbers: `src/lib/utils/formatters.ts`. Never `toFixed` a displayed number in a component.
- Data paths: `$app/paths` `base`. Never a hard-coded leading `/`.
- Legends are controls: click to isolate, click again to reset, `role="button"` + keyboard.
- Every headline number states its direction, units and scope.

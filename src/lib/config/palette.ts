/**
 * Palette — house design system values. A colour means exactly one thing across the app.
 *
 * Sources: Paul Tol bright (colourblind-safe) for chart series and semantic pairs; the
 * bright-on-dark set for anything drawn over the basemap, where marks render 1–4 px wide
 * and chart-weight colours disappear.
 *
 * Four food-group colours differ from the ten-group house set, all four deliberately:
 *
 *   Sugar and Sweeteners (#4fd8e8), Stimulants and Spices (#6aa8ff) are NEW. Canada's
 *   import story is dominated by coffee, cocoa, sugar and spices, which the ten-group
 *   palette folds into "Other"; splitting them out needed two unoccupied hues.
 *
 *   Fruits (#6ef5a0, was #7dde60) and Pulses (#8c4c31, was #c4855c) are MOVED. The house
 *   set puts three colours in green (Fruits, Vegetables, Treenuts) and two in orange-brown
 *   (Oils, Pulses). At OKLab distance those pairs measure 0.079 and 0.089 — below the 0.10
 *   floor for marks drawn 1–4 px wide. That is tolerable where food group is a minor cut;
 *   here it is the app's primary analytical dimension and those groups are compared in
 *   every chart, so both were re-separated. Fruits stays in the produce-green family and
 *   Pulses in the legume-brown family; only the separation changed. Worst pair is now
 *   0.106 and every group clears the map ground by 0.35.
 *
 * scripts/check_palette.py measures all of this and must pass before this file changes.
 */

/** Default rotation for chart series with no fixed meaning. */
export const CHART_COLORS = [
  '#4A9EFF', '#EE6677', '#228833', '#CCBB44', '#66CCEE', '#AA3377', '#BBBBBB',
] as const

/**
 * Trade direction. A fixed semantic triple — these never rotate through CHART_COLORS,
 * because direction is the app's primary axis and must read identically everywhere.
 */
export const DIRECTION_COLORS = {
  import: '#4A9EFF',
  export: '#EE6677',
  within: '#CCBB44',
} as const

/** Transport mode. Used in charts and legends; the map colours by food group or direction. */
export const MODE_COLORS = {
  road: '#228833',
  rail: '#CCBB44',
  maritime: '#4477AA',
  port: '#66CCEE',
  other: '#BBBBBB',
} as const

/** Food groups, bright-on-dark. Order matches meta.foodGroups and the edges.bin fg section. */
export const FOOD_GROUP_COLORS: Record<string, string> = {
  'Grains': '#f5c542',
  'Fruits': '#6ef5a0',
  'Vegetables': '#3dcc3d',
  'Meat and Fish': '#ff6b6b',
  'Dairy and Eggs': '#fff06a',
  'Oils and Oilseed': '#e89840',
  'Pulses': '#8c4c31',
  'Starchy Roots': '#d49ce8',
  'Treenuts': '#5ea54a',
  'Sugar and Sweeteners': '#4fd8e8',
  'Stimulants and Spices': '#6aa8ff',
  'Other': '#aaaaaa',
}

/**
 * Sequential ramp for concentration and volume choropleths. Starts at the page ground so
 * the lowest bucket dissolves into the map rather than reading as a value.
 */
export const SEQUENTIAL_BLUE = [
  '#0a1628', '#0f2847', '#143a66', '#1a4d85', '#2060a5', '#2874c5', '#3a8ee5', '#4A9EFF',
] as const

/** Hex to deck.gl [r,g,b]. */
export function rgb(hex: string): [number, number, number] {
  const h = hex.replace('#', '')
  return [
    parseInt(h.slice(0, 2), 16),
    parseInt(h.slice(2, 4), 16),
    parseInt(h.slice(4, 6), 16),
  ]
}

/** Exports ramp — the export direction colour, darkened toward the ground. */
export const SEQUENTIAL_RED = [
  '#1a0d14', '#33121f', '#4d172a', '#6b1d35', '#8a2541', '#aa3450', '#cc4a62', '#EE6677',
] as const

/** Domestic ramp — the within-Canada direction colour, darkened toward the ground. */
export const SEQUENTIAL_GOLD = [
  '#17150a', '#2b2710', '#403a15', '#57501b', '#6f6721', '#8a8028', '#aa9d34', '#CCBB44',
] as const

/**
 * Choropleth ramp per direction, so a shaded country always reads in its direction's
 * colour: imports blue, exports red, domestic gold. Index 0 is the map ground and is never
 * drawn; the smallest visible share maps to index 1.
 */
export const CHOROPLETH_RAMPS = {
  import: SEQUENTIAL_BLUE,
  export: SEQUENTIAL_RED,
  within: SEQUENTIAL_GOLD,
} as const

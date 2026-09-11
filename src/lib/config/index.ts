/**
 * Config module — the single source of truth for every label, colour, unit, code and
 * definition. Every entry carries a `desc` written for someone who knows food systems but has
 * never seen this tool. Those strings are the app's glossary: layer tooltips, legends, panels
 * and the About panel read from here, so no term can drift between them.
 */
export * from './palette'
import { DIRECTION_COLORS, FOOD_GROUP_COLORS, MODE_COLORS } from './palette'

export const APP = {
  title: 'Canada Food Twin',
  subtitle: 'Where Canada’s food comes from, where it goes, and the routes it takes',
  storageKey: 'canada-food-twin-onboarded',
  hintKeys: {
    clickCountry: 'cft-hint-click-country',
    tryExports: 'cft-hint-try-exports',
  },
  author: { name: 'Kushank Bajaj', url: 'https://kushankbajaj.com' },
  globalApp: 'https://globalfoodsupply.kushankbajaj.com',
  source: 'https://github.com/kushankb/canada-food-twin',
} as const

/** The app's primary axis. Every layer and panel re-reads from the direction toggle. */
export type Direction = 'import' | 'export' | 'within'

export interface DirectionMeta {
  id: Direction
  label: string
  short: string
  flowPhrase: string
  partnerNoun: string
  towards: string
  regionRole: string
  desc: string
}

export const DIRECTIONS: DirectionMeta[] = [
  {
    id: 'import', label: 'Imports', short: 'imports', flowPhrase: 'Canada’s imports',
    partnerNoun: 'Source country', towards: 'from', regionRole: 'Destination province',
    desc: 'Food produced abroad and delivered into Canada. Partners are the countries it is ' +
      'shipped from. Which province it ends up in is allocated by population share, not ' +
      'observed at the border.',
  },
  {
    id: 'export', label: 'Exports', short: 'exports', flowPhrase: 'Canada’s exports',
    partnerNoun: 'Destination', towards: 'to', regionRole: 'Province of origin',
    desc: 'Food produced in Canada and delivered abroad. Partners are the countries it is ' +
      'destined for; provinces are where it is produced, as allocated from production data.',
  },
  {
    id: 'within', label: 'Domestic', short: 'domestic moves', flowPhrase: 'domestic redistribution',
    partnerNoun: 'Province', towards: 'to', regionRole: 'Province',
    desc: 'Redistribution between Canadian provinces. Sparse by construction: the source models ' +
      'surplus-to-deficit movement only, not all domestic distribution.',
  },
]

export const DIRECTION_BY_ID = Object.fromEntries(
  DIRECTIONS.map((d) => [d.id, d]),
) as Record<Direction, DirectionMeta>

export interface FoodGroupMeta { key: string; label: string; color: string; desc: string }

/** Order matches meta.foodGroups and the edges.bin fg section. */
export const FOOD_GROUPS: FoodGroupMeta[] = [
  { key: 'Grains', label: 'Grains',
    desc: 'Wheat, maize, rice, barley, oats, rye, sorghum, millet and products made from them.' },
  { key: 'Fruits', label: 'Fruits',
    desc: 'Fresh and processed fruit, including bananas, citrus, apples, grapes and plantains.' },
  { key: 'Vegetables', label: 'Vegetables',
    desc: 'Tomatoes, onions and the broad “other vegetables” category.' },
  { key: 'Meat and Fish', label: 'Meat & Fish',
    desc: 'Bovine, pig, poultry, sheep and goat meat, edible offal, raw animal fats, finfish, ' +
      'crustaceans, molluscs and fish oils.' },
  { key: 'Dairy and Eggs', label: 'Dairy & Eggs', desc: 'Milk excluding butter, butter and ghee, cream, and eggs.' },
  { key: 'Oils and Oilseed', label: 'Oils & Oilseeds',
    desc: 'Oilseeds and the oils pressed from them — canola/rapeseed, soybean, palm, sunflower, ' +
      'groundnut, coconut, olive, sesame. Canada’s largest group by calories in both directions.' },
  { key: 'Pulses', label: 'Pulses', desc: 'Dry beans, dry peas and other pulses. A major Canadian export.' },
  { key: 'Starchy Roots', label: 'Starchy Roots', desc: 'Potatoes, cassava, sweet potatoes, yams and other roots.' },
  { key: 'Treenuts', label: 'Tree Nuts', desc: 'Tree nuts and nut products.' },
  { key: 'Sugar and Sweeteners', label: 'Sugar & Sweeteners', desc: 'Raw-equivalent sugar and sugar cane.' },
  { key: 'Stimulants and Spices', label: 'Stimulants & Spices',
    desc: 'Coffee, cocoa, tea, pepper, pimento, cloves and other spices — Canada’s tropical ' +
      'import dependence, split out of “Other” so it is visible.' },
  { key: 'Other', label: 'Other', desc: 'Items that fit none of the above; currently wine.' },
].map((g) => ({ ...g, color: FOOD_GROUP_COLORS[g.key] }))

export const FOOD_GROUP_BY_KEY = Object.fromEntries(FOOD_GROUPS.map((g) => [g.key, g])) as Record<string, FoodGroupMeta>

/** Transport modes. Order matches edges_meta codes.mode. */
export const MODES = [
  { key: 'road', label: 'Road', color: MODE_COLORS.road, desc: 'Truck movement on the road network.' },
  { key: 'rail', label: 'Rail', color: MODE_COLORS.rail, desc: 'Rail freight.' },
  { key: 'maritime', label: 'Maritime', color: MODE_COLORS.maritime, desc: 'Deep-sea and coastal shipping legs between ports.' },
  { key: 'port', label: 'Port', color: MODE_COLORS.port, desc: 'Transfer at a port between a sea leg and an inland one.' },
  { key: 'other', label: 'Other', color: MODE_COLORS.other, desc: 'Segments whose mode could not be resolved.' },
] as const

/**
 * How journeys are routed, from the source's four route datasets. Counted once per journey,
 * so these shares are honest in a way that summing segment tonnage by mode is not.
 */
export const ROUTE_TYPES = {
  land_dom: { label: 'Land · direct', color: '#228833',
    desc: 'Moved overland, straight between the partner country and Canada.' },
  land_re: { label: 'Land · re-export', color: '#8cc084',
    desc: 'Moved overland by a country that had imported it first. For imports, the partner ' +
      'shown is that re-exporter, not where the food was grown.' },
  sea_dom: { label: 'Sea · direct', color: '#4477AA',
    desc: 'Shipped by sea, straight between the partner country and Canada.' },
  sea_re: { label: 'Sea · re-export', color: '#8fb3d9',
    desc: 'Shipped by sea by a country that had imported it first. For imports, the partner ' +
      'shown is that re-exporter, not where the food was grown.' },
} as const
export type RouteType = keyof typeof ROUTE_TYPES

/** Concentration vocabulary. These carry the app's analytical claims. */
export const METRIC_DESC = {
  hhi: 'Herfindahl–Hirschman Index: the sum of squared partner shares, from near 0 (spread ' +
    'across many partners) to 1 (one partner supplies everything).',
  effectivePartners: 'The reciprocal of HHI — how many equally sized partners would give the same ' +
    'concentration. 1.8 means Canada trades as if with fewer than two countries, however many ' +
    'appear in the data. Sourcing breadth, not substitutability.',
  dependence: 'The share of Canada’s national tonnage in a food group that this partner accounts for.',
  exposureIndex: 'Calorie share × HHI. Ranks items that are both large and concentrated above those ' +
    'that are only one or the other. A ranking device, not a probability or a forecast.',
  throughput: 'Tonnage on Canada-linked journeys that use this segment. Throughput, not capacity, ' +
    'and not proof the segment is irreplaceable.',
  segmentShare: 'This segment’s tonnage as a share of the whole direction’s trade. Each journey counts ' +
    'once per segment it crosses, so this reads as “share of the trade that passes here”.',
} as const

/** Map layers. `desc` feeds the control-panel tooltips. */
export const LAYERS = {
  routes: {
    label: 'Transport routes', unit: 'click any line for details',
    desc: 'Every road, rail, maritime and port segment on Canada-linked journeys, coloured by the ' +
      'largest food group it carries. Width and brightness are tonnage on a log scale. Straight ' +
      'connector links to region centroids are hidden.',
    source: 'Global Food Twin V8 route allocation',
  },
  partners: {
    label: 'Partner countries', unit: 'shaded by share of trade',
    desc: 'Countries shaded by their share of Canada’s imports or exports in the selected food group, ' +
      'on a log scale. Click a country for its detail and to trace the routes its trade uses.',
    source: 'Global Food Twin V8 origin–destination flows',
  },
  provinces: {
    label: 'Provinces', unit: 'where trade starts or ends',
    desc: 'Provinces shaded by their share of the trade. For exports this follows production — ' +
      'where the food is grown. For imports it is allocated by population share, so every ' +
      'province carries the national partner mix: a population map, not a map of ports of entry.',
    source: 'Global Food Twin V8 origin–destination flows',
  },
} as const
export type LayerKey = keyof typeof LAYERS

/** Boundary tilesets, shared with globalfoodsupply.kushankbajaj.com. */
export const TILESETS = {
  countries: { id: 'kushankb.01l11tz3', layer: 'countries', idKey: 'iso3' },
  admin: { id: 'kushankb.69o1u9mn', layer: 'admin2', idKey: 'ID' },
} as const

export const MAP = {
  darkStyle: 'mapbox://styles/mapbox/dark-v11',
  lightStyle: 'mapbox://styles/mapbox/light-v11',
  initialView: { center: [-80, 38] as [number, number], zoom: 1.7 },
  minZoom: 1,
  maxZoom: 9,
  /**
   * Longitudes east of this are shifted by −360°, so trans-Pacific routes run continuously west
   * from British Columbia instead of breaking at the date line — Asia sits left of Canada, which
   * is how most of that trade travels. 100°E falls east of India and west of the Malacca Strait,
   * so the one unavoidable break lands in the Indian Ocean rather than in the busiest lane.
   */
  foldLongitude: 100,
  defaultWidthScale: 1.0,
} as const

export const HOW_TO = [
  { action: 'Imports / Exports', desc: 'Switch direction — every layer and panel follows' },
  { action: 'Click a country', desc: 'See what Canada trades with it, and trace the routes it uses' },
  { action: 'Click a line', desc: 'See a segment’s tonnage, food groups and partners' },
  { action: 'Click a food group', desc: 'In the legend or the side panel, to show only that group' },
  { action: 'Provinces', desc: 'Turn the layer on and click one to see what enters or leaves there' },
] as const

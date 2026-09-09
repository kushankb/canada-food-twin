/**
 * Config module — the single source of truth for every label, unit, code and definition.
 *
 * Every entry carries a `desc` written for someone who knows food systems but has never
 * seen this tool. Those strings are the app's glossary: legend tooltips, info panels and
 * the About modal all read from here, so no term can drift between them.
 */
export * from './palette'

export const APP = {
  title: 'Canada Food Twin',
  tagline: 'Where Canada’s food comes from, where it goes, and the infrastructure that moves it',
  storageKey: 'canada-food-twin-onboarded',
  sourceUrl: 'https://github.com/kushankb/canada-food-twin',
  globalApp: 'https://globalfoodsupply.kushankbajaj.com',
} as const

/** The app's primary axis. Every view re-reads from the direction toggle. */
export type Direction = 'import' | 'export' | 'within'

export const DIRECTIONS: {
  id: Direction; label: string; verb: string; partnerLabel: string; regionLabel: string; desc: string
}[] = [
  {
    id: 'import', label: 'Imports', verb: 'arriving in Canada', partnerLabel: 'Source country',
    regionLabel: 'Province of arrival',
    desc: 'Food produced abroad and delivered into Canada. Partners are the countries it was ' +
      'produced in; provinces are where the journey ends inside Canada.',
  },
  {
    id: 'export', label: 'Exports', verb: 'leaving Canada', partnerLabel: 'Destination country',
    regionLabel: 'Province of origin',
    desc: 'Food produced in Canada and delivered abroad. Partners are the countries it is ' +
      'destined for; provinces are where the journey begins inside Canada.',
  },
  {
    id: 'within', label: 'Domestic', verb: 'moving inside Canada', partnerLabel: 'Country',
    regionLabel: 'Province',
    desc: 'Redistribution between Canadian provinces. Sparse by construction: the source ' +
      'models surplus-to-deficit movement only, not all domestic distribution.',
  },
]

export const FOOD_GROUP_DESC: Record<string, string> = {
  'Grains': 'Wheat, maize, rice, barley, oats, rye, sorghum, millet and products made from them.',
  'Fruits': 'Fresh and processed fruit, including bananas, citrus, apples, grapes and plantains.',
  'Vegetables': 'Tomatoes, onions and the broad “other vegetables” category.',
  'Meat and Fish': 'All animal flesh and seafood: bovine, pig, poultry, sheep and goat meat, ' +
    'edible offal, raw animal fats, finfish, crustaceans, molluscs and fish oils.',
  'Dairy and Eggs': 'Milk excluding butter, butter and ghee, cream, and eggs.',
  'Oils and Oilseed': 'Oilseeds and the oils pressed from them — canola/rapeseed, soybean, palm, ' +
    'sunflower, groundnut, coconut, olive and sesame. Canada’s largest group by calories in ' +
    'both directions.',
  'Pulses': 'Dry beans, dry peas and other pulses. A major Canadian export.',
  'Starchy Roots': 'Potatoes, cassava, sweet potatoes, yams and other roots.',
  'Treenuts': 'Tree nuts and nut products.',
  'Sugar and Sweeteners': 'Raw-equivalent sugar and sugar cane.',
  'Stimulants and Spices': 'Coffee, cocoa, tea, pepper, pimento, cloves and other spices. ' +
    'Split out from “Other” because these dominate Canada’s tropical import dependence.',
  'Other': 'Items that fit none of the above; currently wine.',
}

export const MODE_DESC: Record<string, string> = {
  road: 'Truck movement on the road network.',
  rail: 'Rail freight.',
  maritime: 'Deep-sea and coastal shipping legs between ports.',
  port: 'Transfer at a port between a maritime leg and an inland one.',
  other: 'Segments whose mode could not be resolved.',
}

/** Concentration vocabulary. These four terms carry the app's analytical claims. */
export const METRIC_DESC = {
  hhi: 'Herfindahl–Hirschman Index: the sum of squared partner shares, from near 0 (spread ' +
    'across many partners) to 1 (a single partner supplies everything).',
  effectivePartners: 'The reciprocal of HHI — how many equally-sized partners would produce the ' +
    'same concentration. 1.8 means Canada sources as if from fewer than two countries, however ' +
    'many appear in the data.',
  partnersFor90: 'How many partners, largest first, it takes to reach 90% of the tonnage. A ' +
    'blunt read on how far the trade would have to be rebuilt if the largest supplier stopped.',
  exposureIndex: 'Calorie share multiplied by HHI. Ranks groups that are both large and ' +
    'concentrated above those that are merely one or the other. A ranking device, not a ' +
    'probability or a forecast.',
  throughput: 'Total tonnage moving through an infrastructure segment on Canada-linked ' +
    'journeys. Not a count of separate shipments, and not a measure of spare capacity.',
} as const

/** Views. Each answers one question nothing else answers. */
export const VIEWS = [
  { id: 'map', label: 'Network', question: 'Which infrastructure carries Canada’s food, and where does it run?' },
  { id: 'concentration', label: 'Concentration', question: 'How many countries does Canada actually depend on?' },
  { id: 'groups', label: 'Food groups', question: 'Does the answer change by what kind of food it is?' },
  { id: 'regions', label: 'Provinces', question: 'Which provinces carry the trade, and in what?' },
  { id: 'exposure', label: 'Exposure', question: 'Where does concentration meet climate and hazard risk?', phase: 2 },
] as const

export type ViewId = (typeof VIEWS)[number]['id']

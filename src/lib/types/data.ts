/** Shapes of the files in static/data/. Written by scripts/build_app_data_v2.py. */
import type { Direction, RouteType } from '../config'

export interface PartnerShare { iso3: string; tonnes: number; share: number }
export interface GroupShare { food_group: string; tonnes: number; share: number }
export interface AdminShare { admin: string; tonnes: number; share: number }
export interface CommodityShare { commodity: string; tonnes: number; share: number }
export type RouteMix = Record<RouteType, number>

export interface Concentration {
  total_tonnes: number
  n_partners: number
  hhi: number
  effective_partners: number | null
  top1: { iso3: string; share: number }
  top3_share: number
  top5_share: number
  partners_for_50pct: number
  partners_for_90pct: number
  top_partners: PartnerShare[]
  kcal?: number
  food_group?: string
}

export type PartnersFile = Record<string, {
  overall: Concentration
  by_food_group: Record<string, Concentration>
  by_commodity: Record<string, Concentration>
}>

export interface CommodityRow {
  commodity: string
  food_group: string
  tonnes: number
  kcal: number | null
  n_partners: number
  hhi: number
  effective_partners: number | null
  top_partner: string
  top_partner_share: number
  partners_for_90pct: number
  calorie_share: number
  exposure_index: number
}

export interface FoodGroupRow {
  food_group: string
  tonnes: number
  kcal: number
  tonne_share: number
  calorie_share: number
  n_commodities: number
  n_partners: number | null
  hhi: number | null
  effective_partners: number | null
  top_partner: string | null
  top_partner_share: number | null
  partners_for_90pct: number | null
  top_partners: PartnerShare[]
  provinces: AdminShare[]
  commodities: CommodityShare[]
  routes: RouteMix | null
  exposure_index: number
}

export interface ProvinceRow {
  admin: string
  name: string
  code: string
  tonnes: number
  kcal: number
  share_of_national: number
  n_partners: number | null
  hhi: number | null
  effective_partners: number | null
  top_partner: string | null
  top_partner_share: number | null
  top_partners: PartnerShare[]
  food_groups: GroupShare[]
  commodities: CommodityShare[]
  routes: RouteMix | null
}

export interface PartnerDetail {
  rank: number
  of: number
  tonnes: number
  kcal: number
  share: number
  food_groups: GroupShare[]
  commodities: CommodityShare[]
  provinces: AdminShare[]
  routes: RouteMix | null
  dependence: { food_group: string; share: number }[]
}

/** direction -> partner iso3 -> detail */
export type PartnerDetailFile = Record<string, Record<string, PartnerDetail>>

/** partners|provinces -> direction -> food group (or "ALL") -> code -> tonnes */
export interface ChoroplethFile {
  partners: Record<string, Record<string, Record<string, number>>>
  provinces: Record<string, Record<string, Record<string, number>>>
}

export interface Place { name: string; lat: number | null; lon: number | null; code?: string }
export interface PlacesFile { countries: Record<string, Place>; provinces: Record<string, Place> }

export interface Headline {
  tonnes: number
  kcal: number
  commodities: number
  food_groups: number
  partners: number
  provinces: number
  hhi: number | null
  effective_partners: number | null
  top_partner: string | null
  top_partner_share: number | null
  routes: RouteMix | null
}

export interface Meta {
  country: string
  tag: string
  partsTag: string
  coverage: string
  units: { tonnes: string; kcal: string }
  foodGroups: string[]
  routeTypes: string[]
  provinces: { admin: string; name: string; code: string }[]
  hasPartnerEdges: boolean
  /** Per direction: is the province partner mix informative, or the national mix split by
   *  demand? Measured by measure_province_mix() in the build. */
  provinceMix?: Record<string, { partner_share_spread: number; allocated: boolean }>
  headline: Record<Direction, Headline>
  caveats: string[]
}

export interface EdgesMeta {
  count: number
  byteLength: number
  sections: Record<string, { offset: number; dtype: string; count: number }>
  codes: {
    direction: string[]; mode: string[]; scope: string[]
    foodGroup: string[]; commodity: string[]
  }
  note: string
  dropped_no_geometry: number
  ecShards: number
  /** direction -> partner code -> number of edges in pe/<direction>/<code>.bin */
  partnerEdges: Record<string, Record<string, number>>
}

/** edges.bin decoded into typed arrays. `coords` is the display copy, Pacific-folded. */
export interface EdgeNetwork {
  count: number
  coords: Float32Array
  tonnes: Float32Array
  kcal: Float32Array
  dir: Uint8Array
  mode: Uint8Array
  scope: Uint8Array
  fg: Uint8Array
  topc: Uint16Array
  meta: EdgesMeta
}

export interface KeyShare { k: string; s: number }
/** Per-edge detail from ec/<shard>.json: top commodities and partners, as shares of the edge. */
export interface EdgeDetail { c: KeyShare[]; p: KeyShare[] }
export type EdgeDetailShard = Record<string, EdgeDetail>

/** pe/<direction>/<code>.bin decoded: every edge a partner's trade uses, heaviest first. */
export interface PartnerEdges { code: string; idx: Uint32Array; tonnes: Float32Array }

export type CommoditiesFile = Record<string, CommodityRow[]>
export type FoodGroupsFile = Record<string, FoodGroupRow[]>
export type ProvincesFile = Record<string, ProvinceRow[]>

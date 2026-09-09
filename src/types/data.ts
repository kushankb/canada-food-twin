/** Shapes of the files in public/data/. Written by scripts/build_app_data_v2.py. */
import type { Direction } from '../config'

export interface PartnerShare { iso3: string; tonnes: number; share: number }

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

export interface PartnersFile {
  [d: string]: {
    overall: Concentration
    by_food_group: Record<string, Concentration>
    by_commodity: Record<string, Concentration>
  }
}

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

export interface KeyedShare { tonnes: number; share: number; [k: string]: string | number }

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
  provinces: KeyedShare[]
  commodities: KeyedShare[]
  modes: KeyedShare[]
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
  food_groups: KeyedShare[]
  commodities: KeyedShare[]
}

export interface Meta {
  country: string
  tag: string
  coverage: string
  units: { tonnes: string; kcal: string }
  foodGroups: string[]
  provinces: { admin: string; name: string; code: string }[]
  headline: Record<Direction, {
    tonnes: number; kcal: number; commodities: number; food_groups: number
    partners: number; provinces: number; hhi: number | null; effective_partners: number | null
  }>
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
}

/** edges.bin, decoded into typed arrays that deck.gl can read without a copy. */
export interface EdgeNetwork {
  count: number
  coords: Float32Array   // lon_a, lat_a, lon_b, lat_b per edge
  tonnes: Float32Array
  kcal: Float32Array
  dir: Uint8Array
  mode: Uint8Array
  scope: Uint8Array
  fg: Uint8Array         // count * foodGroup.length, share 0-255
  topc: Uint16Array
  meta: EdgesMeta
}

export type CommoditiesFile = Record<string, CommodityRow[]>
export type FoodGroupsFile = Record<string, FoodGroupRow[]>
export type ProvincesFile = Record<string, ProvinceRow[]>
export type EdgeCommodityShard = Record<string, { c: string; s: number }[]>

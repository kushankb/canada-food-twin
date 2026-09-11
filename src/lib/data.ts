/**
 * Data loading. The whole payload is fetched once on mount and cached at module level, so every
 * direction / food-group / layer switch is a client-side lookup, never a refetch. Only two things
 * load on demand: the commodity/partner detail for a clicked segment (ec/ shards) and the edge
 * list for a selected partner (pe/ files).
 *
 * Paths go through $app/paths `base`, never a hard-coded leading slash.
 */
import { base } from '$app/paths'
import { MAP } from './config'
import type {
  Meta, PartnersFile, CommoditiesFile, FoodGroupsFile, ProvincesFile, ChoroplethFile,
  PartnerDetailFile, PlacesFile, EdgesMeta, EdgeNetwork, EdgeDetail, EdgeDetailShard,
  PartnerEdges,
} from './types/data'

const cache = new Map<string, Promise<unknown>>()

const url = (p: string) => `${base}/data/${p}`

function once<T>(key: string, load: () => Promise<T>): Promise<T> {
  if (!cache.has(key)) cache.set(key, load())
  return cache.get(key) as Promise<T>
}

async function json<T>(name: string): Promise<T> {
  const r = await fetch(url(name))
  if (!r.ok) throw new Error(`${name}: ${r.status} ${r.statusText}`)
  return r.json() as Promise<T>
}

async function bin(name: string): Promise<ArrayBuffer> {
  const r = await fetch(url(name))
  if (!r.ok) throw new Error(`${name}: ${r.status} ${r.statusText}`)
  return r.arrayBuffer()
}

const fold = (lon: number) => (lon > MAP.foldLongitude ? lon - 360 : lon)

/**
 * Decode edges.bin into typed-array views over one ArrayBuffer. Layout is defined by
 * edges_meta.sections and written by pack_edges() in scripts/build_app_data_v2.py — the two
 * must change together, and a byte-length mismatch throws rather than misreading silently.
 */
async function loadNetwork(): Promise<EdgeNetwork> {
  const [meta, buf] = await Promise.all([json<EdgesMeta>('edges_meta.json'), bin('edges.bin')])
  if (buf.byteLength !== meta.byteLength) {
    throw new Error(
      `edges.bin is ${buf.byteLength} bytes but edges_meta.json expects ${meta.byteLength}. ` +
      'Rerun scripts/build_app_data_v2.py — the two files are out of sync.',
    )
  }
  const view = <T>(name: string, Ctor: new (b: ArrayBuffer, o: number, n: number) => T): T => {
    const s = meta.sections[name]
    return new Ctor(buf, s.offset, s.count)
  }
  const raw = view('coords', Float32Array)
  // Display copy, folded across the Pacific (see MAP.foldLongitude). A segment that still
  // spans more than 180° after folding crosses the fold line; its far end is moved back beside
  // its near end so it draws as a short hop, not a line across the whole map.
  const coords = new Float32Array(raw.length)
  for (let o = 0; o < raw.length; o += 4) {
    const ax = fold(raw[o])
    let bx = fold(raw[o + 2])
    if (bx - ax > 180) bx -= 360
    else if (ax - bx > 180) bx += 360
    coords[o] = ax
    coords[o + 1] = raw[o + 1]
    coords[o + 2] = bx
    coords[o + 3] = raw[o + 3]
  }
  return {
    count: meta.count,
    coords,
    tonnes: view('tonnes', Float32Array),
    kcal: view('kcal', Float32Array),
    dir: view('dir', Uint8Array),
    mode: view('mode', Uint8Array),
    scope: view('scope', Uint8Array),
    fg: view('fg', Uint8Array),
    topc: view('topc', Uint16Array),
    meta,
  }
}

export interface AppData {
  meta: Meta
  partners: PartnersFile
  commodities: CommoditiesFile
  foodgroups: FoodGroupsFile
  provinces: ProvincesFile
  choropleth: ChoroplethFile
  partnerDetail: PartnerDetailFile
  places: PlacesFile
  network: EdgeNetwork
}

export function loadAll(): Promise<AppData> {
  return once('all', async () => {
    const [meta, partners, commodities, foodgroups, provinces, choropleth, partnerDetail, places, network] =
      await Promise.all([
        json<Meta>('meta.json'),
        json<PartnersFile>('partners.json'),
        json<CommoditiesFile>('commodities.json'),
        json<FoodGroupsFile>('foodgroups.json'),
        json<ProvincesFile>('provinces.json'),
        json<ChoroplethFile>('choropleth.json'),
        json<PartnerDetailFile>('partner_detail.json'),
        json<PlacesFile>('places.json'),
        loadNetwork(),
      ])
    return { meta, partners, commodities, foodgroups, provinces, choropleth, partnerDetail, places, network }
  })
}

/** Commodity and partner mix for one segment. One ~58 KB shard per click, then cached. */
export function loadEdgeDetail(index: number, shards: number): Promise<EdgeDetail | null> {
  const shard = index % shards
  return once(`ec-${shard}`, () => json<EdgeDetailShard>(`ec/${shard}.json`))
    .then((s) => s[String(index)] ?? null)
}

/** Every segment a partner's trade uses in one direction: uint32 indices then float32 tonnes. */
export function loadPartnerEdges(direction: string, code: string): Promise<PartnerEdges> {
  return once(`pe-${direction}-${code}`, async () => {
    const buf = await bin(`pe/${direction}/${encodeURIComponent(code)}.bin`)
    const n = buf.byteLength / 8
    return { code, idx: new Uint32Array(buf, 0, n), tonnes: new Float32Array(buf, n * 4, n) }
  })
}

/**
 * Data loading. One fetch of the whole payload on mount, cached at module level, so every
 * direction / food-group / province switch is a client-side lookup and never a refetch.
 *
 * Paths go through import.meta.env.BASE_URL, never a hard-coded leading slash — a literal
 * '/data/...' works in dev and 404s the moment the app is served from anywhere but a
 * domain root.
 */
import { useEffect, useState } from 'react'
import type {
  Meta, PartnersFile, CommoditiesFile, FoodGroupsFile, ProvincesFile,
  EdgesMeta, EdgeNetwork, EdgeCommodityShard,
} from '../types/data'

const cache = new Map<string, Promise<unknown>>()

function url(p: string) {
  return `${import.meta.env.BASE_URL}data/${p}`.replace(/([^:])\/{2,}/g, '$1/')
}

function once<T>(key: string, load: () => Promise<T>): Promise<T> {
  if (!cache.has(key)) cache.set(key, load())
  return cache.get(key) as Promise<T>
}

async function json<T>(name: string): Promise<T> {
  const r = await fetch(url(name))
  if (!r.ok) throw new Error(`${name}: ${r.status} ${r.statusText}`)
  return r.json() as Promise<T>
}

/**
 * Decode edges.bin into typed-array views over one ArrayBuffer. Views, not copies: the
 * 70k-edge network stays a single 2.7 MB allocation that deck.gl reads directly.
 * Layout is defined by edges_meta.sections and written by scripts/build_app_data_v2.py —
 * the two must change together.
 */
async function loadNetwork(): Promise<EdgeNetwork> {
  const meta = await once('edges_meta', () => json<EdgesMeta>('edges_meta.json'))
  const r = await fetch(url('edges.bin'))
  if (!r.ok) throw new Error(`edges.bin: ${r.status} ${r.statusText}`)
  const buf = await r.arrayBuffer()
  if (buf.byteLength !== meta.byteLength) {
    throw new Error(
      `edges.bin is ${buf.byteLength} bytes but edges_meta.json expects ${meta.byteLength}. ` +
      `Rerun scripts/build_app_data_v2.py — the two files are out of sync.`,
    )
  }
  const view = <T>(name: string, Ctor: new (b: ArrayBuffer, o: number, n: number) => T): T => {
    const s = meta.sections[name]
    return new Ctor(buf, s.offset, s.count)
  }
  return {
    count: meta.count,
    coords: view('coords', Float32Array),
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
  network: EdgeNetwork
}

export function loadAll(): Promise<AppData> {
  return once('all', async () => {
    const [meta, partners, commodities, foodgroups, provinces, network] = await Promise.all([
      json<Meta>('meta.json'),
      json<PartnersFile>('partners.json'),
      json<CommoditiesFile>('commodities.json'),
      json<FoodGroupsFile>('foodgroups.json'),
      json<ProvincesFile>('provinces.json'),
      loadNetwork(),
    ])
    return { meta, partners, commodities, foodgroups, provinces, network }
  })
}

/**
 * Per-edge commodity detail, sharded 256 ways. The whole table is ~14 MB — five times the
 * network itself — and only the detail panel ever reads it, one edge at a time. So the
 * shard for the clicked edge is fetched on demand and then cached.
 */
export function loadEdgeCommodities(index: number, shards: number) {
  const shard = index % shards
  return once(`ec-${shard}`, () => json<EdgeCommodityShard>(`ec/${shard}.json`))
    .then((s) => s[String(index)] ?? [])
}

export function useAppData() {
  const [data, setData] = useState<AppData | null>(null)
  const [error, setError] = useState<Error | null>(null)

  useEffect(() => {
    let live = true
    loadAll()
      .then((d) => live && setData(d))
      .catch((e) => live && setError(e instanceof Error ? e : new Error(String(e))))
    return () => { live = false }
  }, [])

  return { data, error, loading: !data && !error }
}

/**
 * Route geometry for the map. Filters the packed network and emits the typed arrays deck.gl's
 * LineLayer reads as binary attributes — no per-edge JavaScript objects for 70k segments.
 */
import type { EdgeNetwork, PartnerEdges } from './types/data'
import { FOOD_GROUPS, rgb } from './config'

export interface RouteFilter {
  direction: number            // code into codes.direction
  foodGroup: number | null     // code into codes.foodGroup, or null for every group
  modes: number[]              // mode codes to keep
  partner: PartnerEdges | null // when set: only this partner's segments, weighted by its tonnes
  widthScale: number
  connectorScope: number       // scope code for connectors, which are never drawn
}

export interface RouteArrays {
  length: number
  index: Uint32Array    // row -> edge index in the network
  source: Float32Array  // lon, lat per row
  target: Float32Array
  colors: Uint8Array    // r, g, b, a per row
  widths: Float32Array  // pixels per row
  weight: Float32Array  // tonnes per row — group- or partner-specific when filtered
  minLog: number
  maxLog: number
  total: number         // sum of weight, for "N segments" captions
}

/** Decades of tonnage the width scale spans below the heaviest visible segment. */
export const WIDTH_DECADES = 5

/** Pixel width at position t in [0, 1] along the log tonnage scale. Shared with the legend. */
export function routeWidth(t: number, scale: number) {
  return (0.35 + 3.4 * Math.pow(t, 1.6)) * scale
}

/** Alpha at the same position: light segments fade so heavy corridors read first. */
export function routeAlpha(t: number) {
  return Math.round(40 + 215 * Math.pow(t, 0.85))
}

const GROUP_RGB = FOOD_GROUPS.map((g) => rgb(g.color))

/** Food group carrying the most tonnage on an edge (fg shares), or Other if none. */
export function dominantGroup(net: EdgeNetwork, i: number): number {
  const G = GROUP_RGB.length
  let best = G - 1
  let bestShare = 0
  for (let g = 0; g < G; g++) {
    const s = net.fg[i * G + g]
    if (s > bestShare) { bestShare = s; best = g }
  }
  return best
}

export function buildRoutes(net: EdgeNetwork, f: RouteFilter): RouteArrays {
  const G = GROUP_RGB.length
  const modeOk = new Uint8Array(256)
  for (const m of f.modes) modeOk[m] = 1

  const w = new Float32Array(net.count)
  if (f.partner) {
    for (let j = 0; j < f.partner.idx.length; j++) w[f.partner.idx[j]] = f.partner.tonnes[j]
  } else {
    w.set(net.tonnes)
  }

  const keep: number[] = []
  let max = 0
  for (let i = 0; i < net.count; i++) {
    let x = w[i]
    if (x <= 0 || net.dir[i] !== f.direction || net.scope[i] === f.connectorScope || !modeOk[net.mode[i]]) {
      w[i] = 0
      continue
    }
    if (f.foodGroup !== null) {
      const s = net.fg[i * G + f.foodGroup]
      if (s === 0) { w[i] = 0; continue }
      x = (x * s) / 255
      w[i] = x
    }
    keep.push(i)
    if (x > max) max = x
  }
  // Heaviest last, so the busiest corridors draw on top.
  keep.sort((a, b) => w[a] - w[b])

  const n = keep.length
  const maxLog = Math.log10(Math.max(max, 10))
  const minLog = maxLog - WIDTH_DECADES
  const out: RouteArrays = {
    length: n,
    index: new Uint32Array(n),
    source: new Float32Array(n * 2),
    target: new Float32Array(n * 2),
    colors: new Uint8Array(n * 4),
    widths: new Float32Array(n),
    weight: new Float32Array(n),
    minLog,
    maxLog,
    total: 0,
  }
  for (let k = 0; k < n; k++) {
    const i = keep[k]
    const o = i * 4
    out.index[k] = i
    out.source[k * 2] = net.coords[o]
    out.source[k * 2 + 1] = net.coords[o + 1]
    out.target[k * 2] = net.coords[o + 2]
    out.target[k * 2 + 1] = net.coords[o + 3]
    const t = Math.min(1, Math.max(0, (Math.log10(Math.max(w[i], 1)) - minLog) / (maxLog - minLog)))
    const c = GROUP_RGB[f.foodGroup ?? dominantGroup(net, i)]
    out.colors[k * 4] = c[0]
    out.colors[k * 4 + 1] = c[1]
    out.colors[k * 4 + 2] = c[2]
    out.colors[k * 4 + 3] = routeAlpha(t)
    out.widths[k] = routeWidth(t, f.widthScale)
    out.weight[k] = w[i]
    out.total += w[i]
  }
  return out
}

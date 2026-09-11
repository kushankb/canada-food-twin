<script lang="ts">
  import {
    FOOD_GROUPS, MODES, DIRECTION_BY_ID, DIRECTION_COLORS, METRIC_DESC, type Direction,
  } from '$lib/config'
  import type { EdgeNetwork, EdgeDetail, Meta, PlacesFile } from '$lib/types/data'
  import { formatTonnes, formatKcal, formatShare } from '$lib/utils/formatters'

  interface Props {
    index: number
    net: EdgeNetwork
    meta: Meta
    places: PlacesFile
    position: { x: number; y: number }
    detail: EdgeDetail | null
    onClose: () => void
  }

  let { index, net, meta, places, position, detail, onClose }: Props = $props()

  const W = 400
  const H = 560
  let x = $derived(Math.min(Math.max(10, position.x - W / 2), window.innerWidth - W - 16))
  let y = $derived(Math.min(Math.max(10, position.y + 18), window.innerHeight - H - 16))

  let G = $derived(net.meta.codes.foodGroup.length)
  let dir = $derived(net.meta.codes.direction[net.dir[index]] as Direction)
  let dm = $derived(DIRECTION_BY_ID[dir])
  let mode = $derived(MODES[net.mode[index]] ?? MODES[MODES.length - 1])
  let scope = $derived(net.meta.codes.scope[net.scope[index]])
  let tonnes = $derived(net.tonnes[index])
  let kcal = $derived(net.kcal[index])
  let national = $derived(meta.headline[dir]?.tonnes ?? 0)
  let share = $derived(national > 0 ? Math.min(1, tonnes / national) : null)

  let groups = $derived(
    FOOD_GROUPS.map((g, gi) => ({ ...g, s: net.fg[index * G + gi] / 255 }))
      .filter((g) => g.s >= 0.005)
      .sort((a, b) => b.s - a.s),
  )

  // Midpoint for a location line, unfolded back to a real longitude.
  let lat = $derived((net.coords[index * 4 + 1] + net.coords[index * 4 + 3]) / 2)
  let lon = $derived.by(() => {
    let l = (net.coords[index * 4] + net.coords[index * 4 + 2]) / 2
    while (l < -180) l += 360
    while (l > 180) l -= 360
    return l
  })
  const coord = (la: number, lo: number) =>
    `${Math.abs(la).toFixed(2)}°${la >= 0 ? 'N' : 'S'}, ${Math.abs(lo).toFixed(2)}°${lo >= 0 ? 'E' : 'W'}`

  let topCommodity = $derived(net.meta.codes.commodity[net.topc[index]])
  // Shares are rounded to 3 dp at build time: a 0 means "below 0.05%", not none. Drop those
  // rows rather than print a false "0%".
  let commodities = $derived((detail?.c ?? []).filter((c) => c.s > 0))
  let partners = $derived((detail?.p ?? []).filter((p) => p.s > 0))
  const partnerName = (k: string) =>
    dir === 'within' ? (places.provinces[k]?.name ?? k) : (places.countries[k]?.name ?? k)
  let partnerTitle = $derived(
    dir === 'import' ? 'Where this food comes from' : dir === 'export' ? 'Where it is going' : 'Destination province',
  )
  let scopeLabel = $derived(scope === 'maritime_port' ? 'Sea or port leg' : 'On Canadian territory')

  // "3.8 Mt" -> ["3.8", "Mt"], so the metric cards keep a short value and a unit label.
  const split = (s: string) => {
    const i = s.indexOf(' ')
    return i < 0 ? [s, ''] : [s.slice(0, i), s.slice(i + 1)]
  }
  let t = $derived(split(formatTonnes(tonnes)))
  let k = $derived(split(formatKcal(kcal)))
</script>

<div class="detail-popup" style="left: {x}px; top: {y}px;" role="dialog" aria-label="Segment detail">
  <button class="detail-close" onclick={onClose} aria-label="Close">&times;</button>

  <div class="detail-header">
    <span class="detail-badge" style="background: {mode.color}">{mode.label}</span>
    <span class="detail-badge" style="background: {DIRECTION_COLORS[dir]}">{dm.label}</span>
    <span class="detail-country">{scopeLabel}</span>
  </div>
  <div class="detail-edge-id">Segment near {coord(lat, lon)}</div>

  <div class="detail-metrics">
    <div class="detail-metric-card">
      <div class="detail-metric-value">{t[0]}</div>
      <div class="detail-metric-label">{t[1] || 'tonnes'}</div>
    </div>
    <div class="detail-metric-card">
      <div class="detail-metric-value">{k[0]}</div>
      <div class="detail-metric-label">{k[1]}</div>
    </div>
    <div class="detail-metric-card" title={METRIC_DESC.segmentShare}>
      <div class="detail-metric-value" style="color: {DIRECTION_COLORS[dir]}">{formatShare(share)}</div>
      <div class="detail-metric-label">of all {dm.short}</div>
    </div>
  </div>

  {#if groups.length}
    <div class="detail-section">
      <div class="detail-section-title">Food groups (by tonnage)</div>
      <div class="detail-bars">
        {#each groups as g}
          <div class="detail-bar-row">
            <div class="detail-bar-label">{g.label}</div>
            <div class="detail-bar-track">
              <div class="detail-bar-fill" style="width: {g.s * 100}%; background: {g.color}"></div>
            </div>
            <div class="detail-bar-value">{formatShare(g.s, 0)}</div>
          </div>
        {/each}
      </div>
    </div>
  {/if}

  <div class="detail-section">
    <div class="detail-section-title">Top commodities</div>
    {#if commodities.length}
      <div class="detail-bars">
        {#each commodities as c}
          <div class="detail-bar-row">
            <div class="detail-bar-label" title={c.k}>{c.k}</div>
            <div class="detail-bar-track">
              <div class="detail-bar-fill" style="width: {c.s * 100}%; background: #c8cdd6"></div>
            </div>
            <div class="detail-bar-value">{formatShare(c.s, 0)}</div>
          </div>
        {/each}
      </div>
    {:else if detail}
      <div class="detail-no-data">Largest: {topCommodity}</div>
    {:else}
      <div class="detail-no-data">Loading… (largest: {topCommodity})</div>
    {/if}
  </div>

  {#if partners.length}
    <div class="detail-section">
      <div class="detail-section-title">{partnerTitle}</div>
      <div class="detail-bars">
        {#each partners as p}
          <div class="detail-bar-row">
            <div class="detail-bar-label" title={partnerName(p.k)}>{partnerName(p.k)}</div>
            <div class="detail-bar-track">
              <div class="detail-bar-fill" style="width: {p.s * 100}%; background: {DIRECTION_COLORS[dir]}"></div>
            </div>
            <div class="detail-bar-value">{formatShare(p.s, 0)}</div>
          </div>
        {/each}
      </div>
    </div>
  {/if}

  <div class="detail-foot">{METRIC_DESC.throughput}</div>
</div>

<style>
  .detail-popup {
    position: fixed;
    z-index: 20;
    width: 400px;
    max-height: 560px;
    overflow-y: auto;
    background: rgba(14, 18, 28, 0.97);
    border: 1px solid rgba(255, 255, 255, 0.12);
    border-radius: 10px;
    padding: 16px 16px 14px;
    color: #e0e0e0;
    font-family: system-ui, -apple-system, sans-serif;
    font-size: 13px;
    backdrop-filter: blur(8px);
    box-shadow: 0 12px 48px rgba(0, 0, 0, 0.55);
  }
  .detail-close {
    position: absolute; top: 8px; right: 10px;
    background: none; border: none; color: #888;
    font-size: 18px; cursor: pointer; line-height: 1; padding: 2px 6px;
  }
  .detail-close:hover { color: #fff; }
  .detail-header {
    display: flex; align-items: center; gap: 6px;
    margin-bottom: 4px; padding-right: 24px; flex-wrap: wrap;
  }
  .detail-badge {
    display: inline-block; font-size: 10px; font-weight: 700;
    text-transform: uppercase; letter-spacing: 0.5px; color: #0a0a0a;
    padding: 2px 8px; border-radius: 3px;
  }
  .detail-country { font-size: 12px; color: #9aa3b2; }
  .detail-edge-id { font-size: 11px; color: #6f7886; margin-bottom: 10px; }
  .detail-metrics { display: grid; grid-template-columns: repeat(3, 1fr); gap: 6px; margin-bottom: 8px; }
  .detail-metric-card { background: rgba(255, 255, 255, 0.05); border-radius: 6px; padding: 8px 10px; text-align: center; }
  .detail-metric-value {
    font-size: 18px; font-weight: 700; color: #fff;
    font-variant-numeric: tabular-nums; line-height: 1.2;
  }
  .detail-metric-label {
    font-size: 10px; color: #7a8494; text-transform: uppercase;
    letter-spacing: 0.4px; margin-top: 2px;
  }
  .detail-section { margin-top: 10px; padding-top: 10px; border-top: 1px solid rgba(255, 255, 255, 0.07); }
  .detail-section-title {
    font-size: 11px; text-transform: uppercase; letter-spacing: 0.5px;
    color: #6f7886; margin-bottom: 6px;
  }
  .detail-bars { display: flex; flex-direction: column; gap: 4px; }
  .detail-bar-row {
    display: grid; grid-template-columns: 128px 1fr 36px;
    align-items: center; gap: 6px; font-size: 11.5px;
  }
  .detail-bar-label { color: #c8cdd6; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
  .detail-bar-track { height: 8px; background: rgba(255, 255, 255, 0.06); border-radius: 2px; overflow: hidden; }
  .detail-bar-fill { height: 100%; border-radius: 2px; transition: width 0.2s ease; }
  .detail-bar-value { color: #c8cdd6; font-variant-numeric: tabular-nums; text-align: right; font-size: 11px; }
  .detail-no-data { font-size: 12px; color: #6f7886; font-style: italic; }
  .detail-foot {
    margin-top: 12px; padding-top: 8px; border-top: 1px solid rgba(255, 255, 255, 0.07);
    font-size: 10.5px; line-height: 1.45; color: #6f7886;
  }
</style>

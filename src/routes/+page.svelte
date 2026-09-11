<script lang="ts">
  import '$lib/styles/map.css'
  import { onMount } from 'svelte'
  import Map from '$lib/components/Map.svelte'
  import ControlPanel from '$lib/components/ControlPanel.svelte'
  import Legend from '$lib/components/Legend.svelte'
  import SidePanel from '$lib/components/SidePanel.svelte'
  import DetailPopup from '$lib/components/DetailPopup.svelte'
  import SearchBar, { type SearchItem } from '$lib/components/SearchBar.svelte'
  import InfoPanel from '$lib/components/InfoPanel.svelte'
  import HowToPanel from '$lib/components/HowToPanel.svelte'
  import Onboarding from '$lib/components/Onboarding.svelte'
  import { loadAll, loadEdgeDetail, loadPartnerEdges, type AppData } from '$lib/data'
  import { buildRoutes } from '$lib/network'
  import {
    DIRECTION_BY_ID, DIRECTION_COLORS, FOOD_GROUP_BY_KEY, MAP, type Direction, type LayerKey,
  } from '$lib/config'
  import { formatCount, formatShare, formatTonnes } from '$lib/utils/formatters'
  import type { EdgeDetail, PartnerEdges } from '$lib/types/data'

  const HAS_TOKEN = !!import.meta.env.PUBLIC_MAPBOX_TOKEN

  // ── Data ────────────────────────────────────────────────────────────────────
  let data = $state.raw<AppData | null>(null)
  let loadError = $state<string | null>(null)
  let mapReady = $state(false)
  let mapCmp = $state<{ flyTo: (lon: number, lat: number, zoom?: number) => void }>()

  onMount(() => {
    loadAll()
      .then((d) => (data = d))
      .catch((e) => (loadError = e instanceof Error ? e.message : String(e)))
  })

  // ── View state. Direction is the primary axis; nothing here triggers a refetch. ──
  let direction = $state<Direction>('import')
  let foodGroup = $state<string | null>(null)
  let layers = $state<Record<LayerKey, boolean>>({ routes: true, partners: true, provinces: false })
  let modes = $state<number[]>([0, 1, 2, 3, 4])
  let widthScale = $state<number>(MAP.defaultWidthScale)
  let selectedCountry = $state<string | null>(null)
  let selectedProvince = $state<string | null>(null)
  let selectedEdge = $state<{ index: number; x: number; y: number } | null>(null)
  let edgeDetail = $state.raw<EdgeDetail | null>(null)
  let partnerEdges = $state.raw<PartnerEdges | null>(null)
  let viewportH = $state(800)

  // ── Routes ──────────────────────────────────────────────────────────────────
  let codes = $derived(data?.network.meta.codes)
  let routes = $derived(
    data && codes
      ? buildRoutes(data.network, {
          direction: codes.direction.indexOf(direction),
          foodGroup: foodGroup ? codes.foodGroup.indexOf(foodGroup) : null,
          modes,
          partner: partnerEdges,
          widthScale,
          connectorScope: codes.scope.indexOf('connector'),
        })
      : null,
  )

  let highlight = $derived.by(() => {
    if (!data || !selectedEdge) return null
    const o = selectedEdge.index * 4
    const c = data.network.coords
    return [c[o], c[o + 1], c[o + 2], c[o + 3]]
  })

  // A selected partner's own segments, when the build carries them (pe/ files).
  $effect(() => {
    const d = data, dir = direction, code = selectedCountry
    partnerEdges = null
    if (!d || !code || dir === 'within' || !d.network.meta.partnerEdges?.[dir]?.[code]) return
    let live = true
    loadPartnerEdges(dir, code).then((pe) => { if (live) partnerEdges = pe }).catch(() => {})
    return () => { live = false }
  })

  // Commodity and partner mix for the clicked segment, fetched on demand.
  $effect(() => {
    const d = data, sel = selectedEdge
    edgeDetail = null
    if (!d || !sel) return
    let live = true
    loadEdgeDetail(sel.index, d.network.meta.ecShards).then((r) => { if (live) edgeDetail = r }).catch(() => {})
    return () => { live = false }
  })

  // ── Choropleth: tonnage -> 0–1 on a four-decade log scale ─────────────────────
  const sum = (o: Record<string, number>) => { let s = 0; for (const k in o) s += o[k]; return s }
  function logScale(o: Record<string, number>) {
    const vals = Object.values(o).filter((v) => v > 0)
    if (!vals.length) return {}
    const hi = Math.log10(Math.max(...vals))
    const lo = hi - 4
    const out: Record<string, number> = {}
    for (const k in o) if (o[k] > 0) out[k] = Math.min(1, Math.max(0, (Math.log10(o[k]) - lo) / (hi - lo)))
    return out
  }

  let partnerTonnes = $derived<Record<string, number>>(
    data && direction !== 'within' ? (data.choropleth.partners[direction]?.[foodGroup ?? 'ALL'] ?? {}) : {},
  )
  let provinceTonnes = $derived<Record<string, number>>(
    data ? (data.choropleth.provinces[direction]?.[foodGroup ?? 'ALL'] ?? {}) : {},
  )
  let partnerTotal = $derived(sum(partnerTonnes))
  let provinceTotal = $derived(sum(provinceTonnes))
  let partnerValues = $derived(logScale(partnerTonnes))
  let provinceValues = $derived(logScale(provinceTonnes))

  let choropleth = $derived.by(() => {
    const dm = DIRECTION_BY_ID[direction]
    const g = foodGroup ? ` · ${FOOD_GROUP_BY_KEY[foodGroup].label}` : ''
    const pick = layers.partners && direction !== 'within' && partnerTotal > 0
      ? { t: partnerTonnes, total: partnerTotal, label: `Partner share of ${dm.short}${g}` }
      : layers.provinces && provinceTotal > 0
        ? { t: provinceTonnes, total: provinceTotal, label: `Province share of ${dm.short}${g}` }
        : null
    if (!pick) return null
    const vals = Object.values(pick.t).filter((v) => v > 0)
    const max = Math.max(...vals)
    return { label: pick.label, min: Math.max(Math.min(...vals), max / 1e4) / pick.total, max: max / pick.total }
  })

  // ── Hover text ──────────────────────────────────────────────────────────────
  const esc = (s: string) =>
    s.replace(/[&<>"]/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' })[c] as string)
  const pct = (x: number) => formatShare(x, x < 0.01 ? 2 : 1)

  function describeCountry(iso: string) {
    if (!data || iso === 'CAN') return null
    const name = esc(data.places.countries[iso]?.name ?? iso)
    if (direction === 'within') return `<div class="popup-title">${name}</div>`
    const dm = DIRECTION_BY_ID[direction]
    const g = foodGroup ? `${FOOD_GROUP_BY_KEY[foodGroup].label.toLowerCase()} ` : ''
    const t = partnerTonnes[iso]
    if (!t) return `<div class="popup-title">${name}</div><div class="popup-desc">No recorded ${g}${dm.short} ${dm.towards} here</div>`
    return `<div class="popup-title">${name}</div>
      <div class="popup-row"><span class="popup-key">Share of Canada’s ${g}${dm.short}</span><span class="popup-value">${pct(t / partnerTotal)}</span></div>
      <div class="popup-row"><span class="popup-key">Tonnage</span><span class="popup-value">${formatTonnes(t)}</span></div>
      <div class="popup-range">Click for detail${data.meta.hasPartnerEdges ? ' and to trace its routes' : ''}</div>`
  }

  function describeProvince(admin: string) {
    if (!data) return null
    const name = esc(data.places.provinces[admin]?.name ?? admin)
    const dm = DIRECTION_BY_ID[direction]
    const g = foodGroup ? `${FOOD_GROUP_BY_KEY[foodGroup].label.toLowerCase()} ` : ''
    const t = provinceTonnes[admin]
    if (!t) return `<div class="popup-title">${name}</div><div class="popup-desc">No recorded ${g}${dm.short} here</div>`
    return `<div class="popup-title">${name}</div>
      <div class="popup-row"><span class="popup-key">Share of Canada’s ${g}${dm.short}</span><span class="popup-value">${pct(t / provinceTotal)}</span></div>
      <div class="popup-row"><span class="popup-key">Tonnage</span><span class="popup-value">${formatTonnes(t)}</span></div>
      <div class="popup-range">${esc(dm.regionRole)} · click for detail</div>`
  }

  // ── Handlers ────────────────────────────────────────────────────────────────
  function onCountryClick(iso: string) {
    if (iso === 'CAN') return
    selectedCountry = selectedCountry === iso ? null : iso
    selectedProvince = null
    selectedEdge = null
  }

  function onProvinceClick(admin: string) {
    selectedProvince = selectedProvince === admin ? null : admin
    selectedCountry = null
    selectedEdge = null
  }

  function setDirection(d: Direction) {
    direction = d
    selectedEdge = null
    if (d === 'within') { selectedCountry = null; layers.provinces = true }
  }

  function toggleLayer(k: LayerKey) {
    layers[k] = !layers[k]
    if (k === 'provinces' && !layers.provinces) selectedProvince = null
  }

  function toggleMode(code: number) {
    modes = modes.includes(code) ? modes.filter((m) => m !== code) : [...modes, code]
  }

  function onSearch(item: SearchItem) {
    selectedEdge = null
    if (item.type === 'country') {
      selectedCountry = item.id
      selectedProvince = null
      layers.partners = true
    } else {
      selectedProvince = item.id
      selectedCountry = null
      layers.provinces = true
    }
    if (item.lat != null && item.lon != null) {
      // Same Pacific fold as the routes, so the camera lands on the copy the lines are drawn on.
      const lon = item.lon > MAP.foldLongitude ? item.lon - 360 : item.lon
      mapCmp?.flyTo(lon, item.lat, item.type === 'country' ? 3 : 4)
    }
  }

  let sidePanelMax = $derived(Math.max(260, viewportH - 64 - 16))
  let tracedName = $derived(selectedCountry && data ? (data.places.countries[selectedCountry]?.name ?? selectedCountry) : null)
</script>

<svelte:window bind:innerHeight={viewportH} />

<div class="loading-overlay {(data && (mapReady || !HAS_TOKEN)) || loadError ? 'hidden' : ''}">
  <div class="loading-spinner"></div>
  <div class="loading-text">Loading Canada’s food network — 70,198 segments…</div>
</div>

<Map
  bind:this={mapCmp}
  {routes}
  {highlight}
  {direction}
  showRoutes={layers.routes}
  showPartners={layers.partners && direction !== 'within'}
  showProvinces={layers.provinces}
  {partnerValues}
  {provinceValues}
  {selectedCountry}
  {selectedProvince}
  onEdgeClick={(index, x, y) => (selectedEdge = { index, x, y })}
  {onCountryClick}
  {onProvinceClick}
  {describeCountry}
  {describeProvince}
  onReady={() => (mapReady = true)}
/>

{#if loadError}
  <div class="map-notice">
    <div class="map-notice-card">
      <h2>Could not load the data</h2>
      {loadError}<br />
      For a local checkout, run <code>python3 scripts/build_app_data_v2.py --tag all</code>.
    </div>
  </div>
{/if}

{#if data}
  <SearchBar places={data.places} partnerDetail={data.partnerDetail} onSelect={onSearch} />

  <ControlPanel
    {direction}
    onDirection={setDirection}
    headline={data.meta.headline[direction]}
    places={data.places}
    {layers}
    onToggle={toggleLayer}
    {modes}
    onToggleMode={toggleMode}
    {widthScale}
    onWidthScale={(v) => (widthScale = v)}
  />

  <InfoPanel caveats={data.meta.caveats} />
  <HowToPanel />

  <SidePanel
    {data}
    {direction}
    {foodGroup}
    onFoodGroup={(k) => (foodGroup = k)}
    {selectedCountry}
    {selectedProvince}
    onClearSelection={() => { selectedCountry = null; selectedProvince = null }}
    traceCount={partnerEdges ? (routes?.length ?? null) : null}
    maxHeight={sidePanelMax}
  />

  {#if partnerEdges && tracedName}
    <div class="trace-banner" style="--dir: {DIRECTION_COLORS[direction]}">
      Showing the <strong>{formatCount(routes?.length)}</strong> segments carrying
      {DIRECTION_BY_ID[direction].short} {DIRECTION_BY_ID[direction].towards} <strong>{tracedName}</strong>{foodGroup ? ` · ${FOOD_GROUP_BY_KEY[foodGroup].label}` : ''}
      — click the country again to clear
    </div>
  {/if}

  {#if selectedEdge}
    <DetailPopup
      index={selectedEdge.index}
      net={data.network}
      meta={data.meta}
      places={data.places}
      position={{ x: selectedEdge.x, y: selectedEdge.y }}
      detail={edgeDetail}
      onClose={() => (selectedEdge = null)}
    />
  {/if}

  <Onboarding {selectedCountry} {direction} />

  <Legend
    showRoutes={layers.routes}
    {routes}
    {widthScale}
    {foodGroup}
    onFoodGroup={(k) => (foodGroup = k)}
    {choropleth}
    {direction}
  />
{/if}

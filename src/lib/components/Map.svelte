<script lang="ts">
  /**
   * Mapbox basemap + deck.gl routes, following globalfoodsupply's Map.svelte:
   *  - routes: deck.gl LineLayer over binary attributes (see $lib/network)
   *  - partner countries and provinces: the shared boundary tilesets, shaded through
   *    feature-state `v` (0–1 on a log scale) so a direction or food-group switch never
   *    rebuilds a layer
   *  - one click handler: a route under the cursor wins, then a province, then a country
   */
  import { onMount } from 'svelte'
  import mapboxgl from 'mapbox-gl'
  import 'mapbox-gl/dist/mapbox-gl.css'
  import { LineLayer } from '@deck.gl/layers'
  import { MapboxOverlay } from '@deck.gl/mapbox'
  import { MAP, TILESETS, CHOROPLETH_RAMPS, type Direction } from '$lib/config'
  import type { RouteArrays } from '$lib/network'

  interface Props {
    routes: RouteArrays | null
    highlight: number[] | null
    direction: Direction
    showRoutes: boolean
    showPartners: boolean
    showProvinces: boolean
    partnerValues: Record<string, number>
    provinceValues: Record<string, number>
    selectedCountry: string | null
    selectedProvince: string | null
    onEdgeClick: (index: number, x: number, y: number) => void
    onCountryClick: (iso3: string) => void
    onProvinceClick: (admin: string) => void
    describeCountry: (iso3: string) => string | null
    describeProvince: (admin: string) => string | null
    onReady?: () => void
  }

  let {
    routes, highlight = null, direction, showRoutes, showPartners, showProvinces,
    partnerValues, provinceValues, selectedCountry = null, selectedProvince = null,
    onEdgeClick, onCountryClick, onProvinceClick, describeCountry, describeProvince,
    onReady = () => {},
  }: Props = $props()

  const TOKEN = import.meta.env.PUBLIC_MAPBOX_TOKEN
  const C = TILESETS.countries
  const A = TILESETS.admin

  let container: HTMLDivElement
  let map = $state.raw<mapboxgl.Map | null>(null)
  let overlay = $state.raw<MapboxOverlay | null>(null)
  let styleReady = $state(false)
  let isDark = $state(true)
  let readyFired = false
  let eventsSetUp = false
  let currentRoutes: RouteArrays | null = null

  const HOVER = ['boolean', ['feature-state', 'hover'], false]
  const SELECTED = ['boolean', ['feature-state', 'selected'], false]
  const HAS_V = ['>=', ['coalesce', ['feature-state', 'v'], -1], 0]

  function rampExpr(dir: Direction): any {
    const r = CHOROPLETH_RAMPS[dir]
    const stops: (number | string)[] = []
    for (let i = 1; i < r.length; i++) stops.push((i - 1) / (r.length - 2), r[i])
    return ['interpolate', ['linear'], ['coalesce', ['feature-state', 'v'], 0], ...stops]
  }

  function outlineColor(): any {
    return isDark
      ? ['case', SELECTED, '#ffffff', HOVER, 'rgba(255,255,255,0.6)', 'rgba(255,255,255,0.14)']
      : ['case', SELECTED, '#0b1020', HOVER, 'rgba(0,0,0,0.55)', 'rgba(0,0,0,0.16)']
  }

  function applyBaseStyleOverrides(m: mapboxgl.Map) {
    const style = m.getStyle()
    if (!style?.layers) return
    for (const layer of style.layers) {
      if (layer.id === 'land' && layer.type === 'background') {
        m.setPaintProperty('land', 'background-color', isDark ? '#0d1120' : '#f0ede8')
      }
      if (layer.id === 'water' && layer.type === 'fill') {
        m.setPaintProperty('water', 'fill-color', isDark ? '#080e1c' : '#c8dce8')
      }
      if ((layer.id.includes('landuse') || layer.id.includes('landcover')) && layer.type === 'fill') {
        m.setPaintProperty(layer.id, 'fill-opacity', 0.3)
      }
      // Our own country and province outlines replace the basemap's admin lines.
      if (layer.id.includes('admin') && layer.type === 'line') {
        m.setLayoutProperty(layer.id, 'visibility', 'none')
      }
    }
    m.setFog(null as any)
  }

  function addSourcesAndLayers(m: mapboxgl.Map) {
    m.addSource('countries', {
      type: 'vector', url: `mapbox://${C.id}`, promoteId: { [C.layer]: C.idKey },
    })
    m.addSource('admin', {
      type: 'vector', url: `mapbox://${A.id}`, promoteId: { [A.layer]: A.idKey },
    })
    // Keep place labels above the shading.
    const before = m.getStyle()?.layers?.find((l) => l.type === 'symbol')?.id
    const notCanada: any = ['!=', ['get', 'iso3'], 'CAN']
    const isCanada: any = ['==', ['get', 'iso3'], 'CAN']

    m.addLayer({
      id: 'partner-fill', type: 'fill', source: 'countries', 'source-layer': C.layer,
      filter: notCanada,
      paint: { 'fill-color': rampExpr(direction), 'fill-opacity': ['case', HOVER, 0.9, HAS_V, 0.72, 0] as any },
    }, before)
    m.addLayer({
      id: 'partner-outline', type: 'line', source: 'countries', 'source-layer': C.layer,
      filter: notCanada,
      paint: { 'line-color': outlineColor(), 'line-width': ['case', SELECTED, 2, HOVER, 1.2, 0.5] as any },
    }, before)
    m.addLayer({
      id: 'canada-fill', type: 'fill', source: 'countries', 'source-layer': C.layer,
      filter: isCanada,
      paint: { 'fill-color': isDark ? '#e8edf4' : '#0b1020', 'fill-opacity': 0.05 },
    }, before)
    m.addLayer({
      id: 'province-fill', type: 'fill', source: 'admin', 'source-layer': A.layer,
      filter: isCanada,
      paint: { 'fill-color': rampExpr(direction), 'fill-opacity': ['case', HOVER, 0.9, HAS_V, 0.72, 0] as any },
    }, before)
    m.addLayer({
      id: 'province-outline', type: 'line', source: 'admin', 'source-layer': A.layer,
      filter: isCanada,
      paint: { 'line-color': outlineColor(), 'line-width': ['case', SELECTED, 2, HOVER, 1.2, 0.4] as any },
    }, before)
    m.addLayer({
      id: 'canada-outline', type: 'line', source: 'countries', 'source-layer': C.layer,
      filter: isCanada,
      paint: { 'line-color': isDark ? 'rgba(255,255,255,0.7)' : 'rgba(0,0,0,0.6)', 'line-width': 1.2 },
    }, before)
  }

  function hoverLayer(
    m: mapboxgl.Map, popup: mapboxgl.Popup, layerId: string, source: string,
    sourceLayer: string, idKey: string, describe: (id: string) => string | null,
  ) {
    let hovered: string | number | null = null
    m.on('mousemove', layerId, (e) => {
      const f = e.features?.[0]
      if (!f) return
      if (hovered !== null && hovered !== f.id) m.setFeatureState({ source, sourceLayer, id: hovered }, { hover: false })
      hovered = f.id ?? null
      if (hovered !== null) m.setFeatureState({ source, sourceLayer, id: hovered }, { hover: true })
      m.getCanvas().style.cursor = 'pointer'
      const html = describe(String(f.properties?.[idKey]))
      if (html) popup.setLngLat(e.lngLat).setHTML(html).addTo(m)
      else popup.remove()
    })
    m.on('mouseleave', layerId, () => {
      if (hovered !== null) m.setFeatureState({ source, sourceLayer, id: hovered }, { hover: false })
      hovered = null
      m.getCanvas().style.cursor = ''
      popup.remove()
    })
  }

  function handleClick(m: mapboxgl.Map, ov: MapboxOverlay, e: mapboxgl.MapMouseEvent) {
    const picked = ov.pickObject({ x: e.point.x, y: e.point.y, radius: 6, layerIds: ['routes'] })
    if (picked && picked.index >= 0 && currentRoutes) {
      onEdgeClick(currentRoutes.index[picked.index], e.point.x, e.point.y)
      return
    }
    if (m.getLayer('province-fill') && showProvinces) {
      const f = m.queryRenderedFeatures(e.point, { layers: ['province-fill'] })
      if (f.length) { onProvinceClick(String(f[0].properties?.[A.idKey])); return }
    }
    if (m.getLayer('partner-fill') && showPartners) {
      const f = m.queryRenderedFeatures(e.point, { layers: ['partner-fill'] })
      if (f.length) { onCountryClick(String(f[0].properties?.[C.idKey])); return }
    }
  }

  export function flyTo(lon: number, lat: number, zoom = 4) {
    map?.flyTo({ center: [lon, lat], zoom, duration: 1400, essential: true })
  }

  function toggleStyle() {
    if (!map) return
    isDark = !isDark
    styleReady = false
    prevPartner = new Set()
    prevProvince = new Set()
    selCountry = null
    selProvince = null
    map.setStyle(isDark ? MAP.darkStyle : MAP.lightStyle)
  }

  onMount(() => {
    if (!TOKEN) return
    mapboxgl.accessToken = TOKEN
    const m = new mapboxgl.Map({
      container,
      style: MAP.darkStyle,
      center: MAP.initialView.center,
      zoom: MAP.initialView.zoom,
      minZoom: MAP.minZoom,
      maxZoom: MAP.maxZoom,
      projection: 'mercator',
      antialias: true,
      hash: true,
    })
    const ov = new MapboxOverlay({ interleaved: true, layers: [] })
    m.addControl(ov)
    m.addControl(new mapboxgl.NavigationControl({ showCompass: false }), 'top-right')
    const popup = new mapboxgl.Popup({ closeButton: false, closeOnClick: false, maxWidth: '300px', offset: 12 })

    m.on('style.load', () => {
      applyBaseStyleOverrides(m)
      addSourcesAndLayers(m)
      if (!eventsSetUp) {
        hoverLayer(m, popup, 'partner-fill', 'countries', C.layer, C.idKey, (id) => describeCountry(id))
        hoverLayer(m, popup, 'province-fill', 'admin', A.layer, A.idKey, (id) => describeProvince(id))
        m.on('click', (e) => handleClick(m, ov, e))
        eventsSetUp = true
      }
      styleReady = true
      if (!readyFired) { readyFired = true; onReady() }
    })

    map = m
    overlay = ov
    return () => {
      m.remove()
      map = null
      overlay = null
      styleReady = false
      eventsSetUp = false
    }
  })

  // ── deck.gl routes ────────────────────────────────────────────────────────
  $effect(() => {
    const ov = overlay
    void styleReady // re-set layers after a basemap swap
    const r = routes
    const hl = highlight
    const on = showRoutes
    if (!ov) return
    currentRoutes = r
    const layers: LineLayer<any>[] = []
    if (on && r && r.length) {
      layers.push(new LineLayer({
        id: 'routes',
        data: {
          length: r.length,
          attributes: {
            getSourcePosition: { value: r.source, size: 2 },
            getTargetPosition: { value: r.target, size: 2 },
            getColor: { value: r.colors, size: 4, normalized: true },
            getWidth: { value: r.widths, size: 1 },
          },
        } as any,
        widthUnits: 'pixels',
        widthMinPixels: 0.3,
        widthMaxPixels: 9,
        pickable: true,
        autoHighlight: true,
        highlightColor: [255, 255, 255, 170],
        parameters: { depthTest: false } as any,
      }))
    }
    if (hl) {
      layers.push(new LineLayer({
        id: 'selected-edge',
        data: [hl],
        getSourcePosition: (d: number[]) => [d[0], d[1]],
        getTargetPosition: (d: number[]) => [d[2], d[3]],
        getColor: [255, 255, 255, 255],
        getWidth: 5,
        widthUnits: 'pixels',
        parameters: { depthTest: false } as any,
      }))
    }
    ov.setProps({ layers })
  })

  // ── Choropleth values through feature-state ──────────────────────────────
  let prevPartner = new Set<string>()
  let prevProvince = new Set<string>()

  function syncValues(m: mapboxgl.Map, source: string, sourceLayer: string,
                      vals: Record<string, number>, prev: Set<string>) {
    for (const id of prev) if (!(id in vals)) m.removeFeatureState({ source, sourceLayer, id }, 'v')
    for (const id in vals) m.setFeatureState({ source, sourceLayer, id }, { v: vals[id] })
    return new Set(Object.keys(vals))
  }

  $effect(() => {
    const m = map, vals = partnerValues
    if (!m || !styleReady) return
    prevPartner = syncValues(m, 'countries', C.layer, vals, prevPartner)
  })

  $effect(() => {
    const m = map, vals = provinceValues
    if (!m || !styleReady) return
    prevProvince = syncValues(m, 'admin', A.layer, vals, prevProvince)
  })

  $effect(() => {
    const m = map, dir = direction
    if (!m || !styleReady) return
    const e = rampExpr(dir)
    m.setPaintProperty('partner-fill', 'fill-color', e)
    m.setPaintProperty('province-fill', 'fill-color', e)
  })

  $effect(() => {
    const m = map, p = showPartners, v = showProvinces
    if (!m || !styleReady) return
    const vis = (id: string, on: boolean) => m.setLayoutProperty(id, 'visibility', on ? 'visible' : 'none')
    vis('partner-fill', p)
    vis('partner-outline', p)
    vis('province-fill', v)
    vis('province-outline', v)
  })

  // ── Selection outlines ───────────────────────────────────────────────────
  let selCountry: string | null = null
  let selProvince: string | null = null

  $effect(() => {
    const m = map, id = selectedCountry
    if (!m || !styleReady) return
    if (selCountry && selCountry !== id) m.setFeatureState({ source: 'countries', sourceLayer: C.layer, id: selCountry }, { selected: false })
    if (id) m.setFeatureState({ source: 'countries', sourceLayer: C.layer, id }, { selected: true })
    selCountry = id
  })

  $effect(() => {
    const m = map, id = selectedProvince
    if (!m || !styleReady) return
    if (selProvince && selProvince !== id) m.setFeatureState({ source: 'admin', sourceLayer: A.layer, id: selProvince }, { selected: false })
    if (id) m.setFeatureState({ source: 'admin', sourceLayer: A.layer, id }, { selected: true })
    selProvince = id
  })
</script>

<div bind:this={container} id="map"></div>

{#if !TOKEN}
  <div class="map-notice">
    <div class="map-notice-card">
      <h2>Basemap unavailable</h2>
      No Mapbox token was set when this build was made. Add <code>PUBLIC_MAPBOX_TOKEN</code> to
      <code>.env</code> locally, or as a repository secret for the deployed site, and rebuild.
    </div>
  </div>
{:else}
  <button
    class="style-toggle"
    onclick={toggleStyle}
    title={isDark ? 'Switch to light map' : 'Switch to dark map'}
  >
    {isDark ? '☀ Light map' : '🌙 Dark map'}
  </button>
{/if}

<style>
  .style-toggle {
    position: absolute;
    bottom: 70px;
    left: 16px;
    z-index: 8;
    background: rgba(14, 18, 28, 0.92);
    border: 1px solid rgba(255, 255, 255, 0.14);
    border-radius: 7px;
    cursor: pointer;
    font-size: 0.72rem;
    font-weight: 500;
    color: #c8cdd6;
    font-family: system-ui, -apple-system, sans-serif;
    padding: 6px 14px;
    backdrop-filter: blur(8px);
    transition: all 0.15s;
    white-space: nowrap;
  }
  .style-toggle:hover {
    background: rgba(100, 210, 255, 0.1);
    border-color: rgba(100, 210, 255, 0.3);
    color: #fff;
  }
</style>

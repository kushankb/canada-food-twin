<script lang="ts">
  import {
    APP, DIRECTIONS, DIRECTION_COLORS, LAYERS, MODES, type Direction, type LayerKey,
  } from '$lib/config'
  import type { Headline, PlacesFile } from '$lib/types/data'
  import {
    formatTonnes, formatEffective, formatShare, formatCount, describeHHI,
  } from '$lib/utils/formatters'

  interface Props {
    direction: Direction
    onDirection: (d: Direction) => void
    headline: Headline | undefined
    places: PlacesFile
    layers: Record<LayerKey, boolean>
    onToggle: (key: LayerKey) => void
    modes: number[]
    onToggleMode: (code: number) => void
    widthScale: number
    onWidthScale: (v: number) => void
  }

  let {
    direction, onDirection, headline, places, layers, onToggle, modes, onToggleMode,
    widthScale, onWidthScale,
  }: Props = $props()

  let tooltipKey = $state<LayerKey | null>(null)
  let tooltipPos = $state({ top: 0, left: 0 })
  let infoVisible = $state(false)
  let infoPos = $state({ top: 0, left: 0 })

  function showTooltip(e: MouseEvent, key: LayerKey) {
    const r = (e.currentTarget as HTMLElement).getBoundingClientRect()
    tooltipPos = { top: r.top + r.height / 2, left: r.right + 12 }
    tooltipKey = key
  }

  function showInfo(e: MouseEvent) {
    const r = (e.currentTarget as HTMLElement).getBoundingClientRect()
    infoPos = { top: r.bottom + 6, left: r.left }
    infoVisible = true
  }

  let color = $derived(DIRECTION_COLORS[direction])
  let topName = $derived(
    headline?.top_partner ? (places.countries[headline.top_partner]?.name ?? headline.top_partner) : null,
  )
  const LAYER_ORDER: LayerKey[] = ['routes', 'partners', 'provinces']
  // Road, rail, maritime, port. "Other" stays on: it is unresolved, not a choice.
  const CHIP_MODES = MODES.slice(0, 4)
</script>

<div class="control-panel" style="--dir: {color}">
  <div class="panel-header">
    <div class="panel-title">{APP.title}</div>
    <button class="info-btn" onmouseenter={showInfo} onmouseleave={() => (infoVisible = false)}
      aria-label="About this data">ⓘ</button>
  </div>
  <div class="panel-subtitle">{APP.subtitle}</div>

  <div class="dir-toggle" role="radiogroup" aria-label="Trade direction">
    {#each DIRECTIONS as d}
      <button
        role="radio"
        aria-checked={d.id === direction}
        aria-label={d.label}
        class="dir-btn {d.id === direction ? 'active' : ''} {d.id === 'within' ? 'minor' : ''}"
        style="--btn-color: {DIRECTION_COLORS[d.id]}"
        title={d.desc}
        onclick={() => onDirection(d.id)}
      >{d.label}</button>
    {/each}
  </div>

  {#if headline}
    <div class="headline">
      {#if direction === 'within'}
        <strong>{formatTonnes(headline.tonnes)}</strong> redistributed between provinces. Sparse by
        construction — the source models surplus-to-deficit moves only.
      {:else}
        <strong>{formatTonnes(headline.tonnes)}</strong>
        {direction === 'import' ? 'from' : 'to'} <strong>{formatCount(headline.partners)}</strong> countries,
        as concentrated as <span class="accent">{formatEffective(headline.effective_partners)}</span>
        equal-sized {direction === 'import' ? 'suppliers' : 'buyers'} ({describeHHI(headline.hhi)}).
        {#if topName}
          <strong>{topName}</strong> alone {direction === 'import' ? 'supplies' : 'takes'}
          <span class="accent">{formatShare(headline.top_partner_share)}</span>.
        {/if}
      {/if}
    </div>
  {/if}

  <hr class="panel-divider" />
  <div class="panel-section-label">Map layers</div>

  {#each LAYER_ORDER as key}
    {@const L = LAYERS[key]}
    {@const unavailable = key === 'partners' && direction === 'within'}
    <div class="layer-btn-wrapper">
      <button
        class="layer-btn {layers[key] && !unavailable ? 'active' : ''}"
        style="--btn-color: {key === 'routes' ? '#d8dde6' : color}; {unavailable ? 'opacity: 0.45' : ''}"
        onclick={() => onToggle(key)}
        onmouseenter={(e) => showTooltip(e, key)}
        onmouseleave={() => (tooltipKey = null)}
        aria-pressed={layers[key]}
        aria-label={`${L.label} — ${unavailable ? 'not used for domestic moves' : L.unit}`}
      >
        <span class="layer-dot"></span>
        <span class="layer-btn-text">
          <span class="layer-btn-label">{L.label}</span>
          <span class="layer-btn-unit">{unavailable ? 'not used for domestic moves' : L.unit}</span>
        </span>
      </button>
    </div>

    {#if key === 'routes' && layers.routes}
      <div class="slider-label-row">
        <span>Line thickness</span>
        <span class="opacity-value">{widthScale.toFixed(1)}×</span>
      </div>
      <div class="opacity-slider-row">
        <input
          type="range"
          class="opacity-slider"
          min="0.3" max="2.5" step="0.1"
          value={widthScale}
          oninput={(e) => onWidthScale(parseFloat((e.target as HTMLInputElement).value))}
          style="--slider-color: #d8dde6"
          aria-label="Line thickness"
        />
      </div>
      <div class="mode-chips" role="group" aria-label="Transport modes">
        {#each CHIP_MODES as m, code}
          <button
            class="mode-chip {modes.includes(code) ? '' : 'off'}"
            style="--chip-color: {m.color}"
            onclick={() => onToggleMode(code)}
            aria-pressed={modes.includes(code)}
            title={`${modes.includes(code) ? 'Hide' : 'Show'} ${m.label.toLowerCase()} segments — ${m.desc}`}
          ><span class="dot"></span>{m.label}</button>
        {/each}
      </div>
    {/if}
  {/each}
</div>

{#if tooltipKey}
  {@const info = LAYERS[tooltipKey]}
  <div class="layer-tooltip" style="top: {tooltipPos.top}px; left: {tooltipPos.left}px; transform: translate(0, -50%)">
    {info.desc}
    <span class="tooltip-source">{info.source}</span>
  </div>
{/if}

{#if infoVisible}
  <div class="layer-tooltip" style="top: {infoPos.top}px; left: {infoPos.left}px">
    Directional food flows for Canada from the Global Food Twin — imports and exports separated,
    single-counted, for every segment they use.
    <span class="tooltip-source">Global Food Twin V8 · FAO Food Balance Sheets</span>
  </div>
{/if}

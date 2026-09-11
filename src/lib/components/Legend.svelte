<script lang="ts">
  /**
   * One wide, short card along the bottom: food-group key (also the filter), the route-width
   * scale, and the partner/province shading scale. Kept low so it covers the South Atlantic
   * rather than the Canada–US border, where most of the import routes run.
   */
  import { FOOD_GROUPS, CHOROPLETH_RAMPS, type Direction } from '$lib/config'
  import { routeWidth, routeAlpha, type RouteArrays } from '$lib/network'
  import { formatTonnes, formatShare } from '$lib/utils/formatters'

  interface Props {
    showRoutes: boolean
    routes: RouteArrays | null
    widthScale: number
    foodGroup: string | null
    onFoodGroup: (key: string | null) => void
    choropleth: { label: string; min: number; max: number } | null
    direction: Direction
  }

  let { showRoutes, routes, widthScale, foodGroup, onFoodGroup, choropleth, direction }: Props = $props()

  function toggle(key: string) {
    onFoodGroup(foodGroup === key ? null : key)
  }

  // Four reference widths along the same log scale the routes use.
  let samples = $derived.by(() => {
    if (!routes || !routes.length) return []
    const r = routes
    return [0.2, 0.55, 0.8, 1].map((t) => ({
      tonnes: Math.pow(10, r.minLog + t * (r.maxLog - r.minLog)),
      px: routeWidth(t, widthScale),
      alpha: routeAlpha(t) / 255,
    }))
  })

  let ramp = $derived(CHOROPLETH_RAMPS[direction].slice(1).join(', '))
</script>

<div class="legend-stack">
  <div class="legend legend-wide">
    <div class="legend-head">
      <span class="legend-title">Food group</span>
      <span class="legend-sub">
        {showRoutes ? 'route colour = largest group on each segment' : 'filters the shading and panels'}
      </span>
    </div>
    <div class="legend-swatches four">
      {#each FOOD_GROUPS as g}
        <div
          class="legend-swatch-row clickable {foodGroup && foodGroup !== g.key ? 'dimmed' : ''} {foodGroup === g.key ? 'selected' : ''}"
          role="button"
          tabindex="0"
          title={foodGroup === g.key ? 'Click to show all food groups' : `Click to show only ${g.label} — ${g.desc}`}
          onclick={() => toggle(g.key)}
          onkeydown={(e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); toggle(g.key) } }}
        >
          <span class="legend-swatch" style="background: {g.color}"></span>
          <span class="legend-swatch-label">{g.label}</span>
        </div>
      {/each}
    </div>

    {#if (showRoutes && samples.length) || choropleth}
      <div class="legend-row">
        {#if showRoutes && samples.length}
          <div>
            <div class="legend-title small">Tonnes on segment{foodGroup ? ' (this group)' : ''}</div>
            <div class="width-scale">
              {#each samples as s}
                <div class="width-sample">
                  <span class="line" style="height: {Math.max(1, s.px)}px; opacity: {s.alpha}"></span>
                  <span class="lbl">{formatTonnes(s.tonnes)}</span>
                </div>
              {/each}
            </div>
          </div>
        {/if}
        {#if choropleth}
          <div>
            <div class="legend-title small">{choropleth.label}</div>
            <div class="legend-gradient" style="background: linear-gradient(to right, {ramp})"></div>
            <div class="legend-labels">
              <span>{formatShare(choropleth.min, 2)}</span><span>{formatShare(choropleth.max)}</span>
            </div>
          </div>
        {/if}
      </div>
    {/if}

    <div class="legend-hint {foodGroup ? 'faded' : 'pulse'}">
      {foodGroup ? 'Click the selected group to reset' : 'Click a food group to filter'} · widths and shading on log scales
    </div>
  </div>
</div>

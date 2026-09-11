<script lang="ts">
  import { APP, METRIC_DESC } from '$lib/config'

  let { caveats = [] }: { caveats?: string[] } = $props()
  let open = $state(false)
</script>

<div class="info-panel">
  <button class="info-toggle" onclick={() => (open = !open)}>
    {open ? '✕ Close' : 'ℹ About this map'}
  </button>

  {#if open}
    <div class="info-content">
      <p class="info-desc">
        This map follows Canada’s food trade — imports and exports — along the roads, railways,
        shipping lanes and ports that carry it, split into twelve food groups. Unlike the
        <a class="info-cite-link" href={APP.globalApp} target="_blank" rel="noopener noreferrer">global map</a>,
        every number here is directional and counted once: an import is an import.
      </p>

      <div class="info-section-title">Reading concentration</div>
      <p class="info-desc">{METRIC_DESC.effectivePartners}</p>

      <div class="info-section-title">What the numbers are not</div>
      <ul class="info-caveats">
        {#each caveats as c}<li>{c}</li>{/each}
      </ul>

      <div class="info-section-title">Data sources</div>
      <div class="info-sources">
        <div class="info-source-row">
          <span class="info-source-label">Trade flows</span>
          <span class="info-source-value">Global Food Twin V8 route allocation, built on FAO Food Balance Sheets</span>
        </div>
        <div class="info-source-row">
          <span class="info-source-label">Food groups</span>
          <span class="info-source-value">82 FBS commodities mapped to 12 groups</span>
        </div>
        <div class="info-source-row">
          <span class="info-source-label">Boundaries</span>
          <span class="info-source-value">Country and province tilesets shared with Global Food Supply</span>
        </div>
        <div class="info-source-row">
          <span class="info-source-label">Basemap</span>
          <span class="info-source-value">© Mapbox © OpenStreetMap</span>
        </div>
      </div>

      <div class="info-built-by">
        Built by
        <a href={APP.author.url} target="_blank" rel="noopener noreferrer" class="info-cite-link">{APP.author.name}</a>
        · <a href={APP.source} target="_blank" rel="noopener noreferrer" class="info-cite-link">Source</a>
      </div>
    </div>
  {/if}
</div>

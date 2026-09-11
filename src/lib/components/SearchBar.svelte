<script lang="ts">
  import type { PlacesFile, PartnerDetailFile } from '$lib/types/data'

  export interface SearchItem {
    type: 'country' | 'province'
    id: string
    name: string
    sub: string
    lat: number | null
    lon: number | null
  }

  interface Props {
    places: PlacesFile
    partnerDetail: PartnerDetailFile
    onSelect: (item: SearchItem) => void
  }

  let { places, partnerDetail, onSelect }: Props = $props()

  let query = $state('')
  let focused = $state(false)
  let selectedIdx = $state(-1)

  // Every trading partner plus the 13 provinces; each country tagged with its ranks.
  let index = $derived.by(() => {
    const items: (SearchItem & { search: string })[] = []
    const codes = new Set([...Object.keys(partnerDetail.import ?? {}), ...Object.keys(partnerDetail.export ?? {})])
    for (const iso of codes) {
      const p = places.countries[iso]
      if (!p) continue
      const ri = partnerDetail.import?.[iso]?.rank
      const re = partnerDetail.export?.[iso]?.rank
      const sub = [ri ? `imports #${ri}` : '', re ? `exports #${re}` : ''].filter(Boolean).join(' · ')
      items.push({ type: 'country', id: iso, name: p.name, sub, lat: p.lat, lon: p.lon, search: `${p.name} ${iso}`.toLowerCase() })
    }
    for (const [adm, p] of Object.entries(places.provinces)) {
      items.push({ type: 'province', id: adm, name: p.name, sub: p.code ?? '', lat: p.lat, lon: p.lon,
        search: `${p.name} ${p.code ?? ''}`.toLowerCase() })
    }
    return items
  })

  let results = $derived.by(() => {
    const q = query.trim().toLowerCase()
    if (q.length < 2) return []
    return index
      .filter((it) => it.search.includes(q))
      .sort((a, b) => {
        const as = a.search.startsWith(q) ? 0 : 1
        const bs = b.search.startsWith(q) ? 0 : 1
        if (as !== bs) return as - bs
        if (a.type !== b.type) return a.type === 'province' ? -1 : 1
        return a.name.localeCompare(b.name)
      })
      .slice(0, 8)
  })

  function pick(item: SearchItem) {
    query = ''
    focused = false
    selectedIdx = -1
    onSelect(item)
  }

  function onKeydown(e: KeyboardEvent) {
    if (e.key === 'ArrowDown') { e.preventDefault(); selectedIdx = Math.min(selectedIdx + 1, results.length - 1) }
    else if (e.key === 'ArrowUp') { e.preventDefault(); selectedIdx = Math.max(selectedIdx - 1, -1) }
    else if ((e.key === 'Enter' || e.keyCode === 13) && results[Math.max(selectedIdx, 0)]) { e.preventDefault(); pick(results[Math.max(selectedIdx, 0)]) }
    else if (e.key === 'Escape') { query = '' }
  }
</script>

<div class="search-wrapper">
  <div class="search-input-row">
    <svg class="search-icon" viewBox="0 0 20 20" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true">
      <circle cx="8.5" cy="8.5" r="5.5" />
      <line x1="13" y1="13" x2="18" y2="18" />
    </svg>
    <input
      type="text"
      class="search-input"
      placeholder="Search a partner country or province…"
      aria-label="Search a partner country or province"
      bind:value={query}
      onfocus={() => (focused = true)}
      onblur={() => setTimeout(() => (focused = false), 150)}
      onkeydown={onKeydown}
    />
  </div>

  {#if focused && results.length > 0}
    <div class="search-results" role="listbox">
      {#each results as item, i}
        <button class="search-result {i === selectedIdx ? 'highlighted' : ''}" role="option"
          aria-selected={i === selectedIdx} onmousedown={() => pick(item)}>
          <span class="sr-badge">{item.type === 'country' ? 'Country' : 'Province'}</span>
          <span class="sr-name">{item.name}</span>
          <span class="sr-sub">{item.sub}</span>
        </button>
      {/each}
    </div>
  {/if}
</div>

<style>
  .search-wrapper { position: absolute; top: 16px; left: 50%; transform: translateX(-50%); z-index: 7; width: 340px; }
  .search-input-row {
    display: flex; align-items: center;
    background: rgba(14, 18, 28, 0.92); border: 1px solid rgba(255, 255, 255, 0.12);
    border-radius: 8px; padding: 0 10px; backdrop-filter: blur(8px);
  }
  .search-icon { width: 16px; height: 16px; color: #6f7886; flex-shrink: 0; }
  .search-input {
    flex: 1; background: none; border: none; color: #e0e0e0; font-size: 13px;
    padding: 9px 8px; outline: none; font-family: system-ui, -apple-system, sans-serif;
  }
  .search-input::placeholder { color: #6f7886; }
  .search-results {
    margin-top: 4px; background: rgba(14, 18, 28, 0.96); border: 1px solid rgba(255, 255, 255, 0.12);
    border-radius: 8px; overflow: hidden; box-shadow: 0 8px 32px rgba(0, 0, 0, 0.4);
  }
  .search-result {
    display: flex; align-items: center; gap: 8px; width: 100%; padding: 8px 12px;
    background: none; border: none; color: #c8cdd6; font-size: 12px; text-align: left;
    cursor: pointer; font-family: inherit; border-bottom: 1px solid rgba(255, 255, 255, 0.04);
  }
  .search-result:last-child { border-bottom: none; }
  .search-result:hover, .search-result.highlighted { background: rgba(100, 210, 255, 0.08); }
  .sr-badge {
    font-size: 9px; text-transform: uppercase; letter-spacing: 0.5px; color: #64d2ff;
    background: rgba(100, 210, 255, 0.12); padding: 1px 5px; border-radius: 3px; flex-shrink: 0;
  }
  .sr-name { color: #fff; font-weight: 500; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
  .sr-sub { color: #6f7886; font-size: 11px; margin-left: auto; flex-shrink: 0; }
</style>

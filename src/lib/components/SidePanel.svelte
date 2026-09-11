<script lang="ts">
  /**
   * Right-hand panel. With nothing selected it is Canada's overview for the current direction —
   * concentration, route mix, and the food-group table that answers "does it change by what kind
   * of food it is?". Selecting a country or province swaps in that place's detail, following
   * globalfoodsupply's DistrictPanel.
   */
  import {
    DIRECTION_BY_ID, DIRECTION_COLORS, FOOD_GROUP_BY_KEY, METRIC_DESC, ROUTE_TYPES,
    type Direction, type RouteType,
  } from '$lib/config'
  import type { AppData } from '$lib/data'
  import type { RouteMix } from '$lib/types/data'
  import {
    describeHHI, formatCount, formatEffective, formatKcal, formatShare, formatTonnes,
  } from '$lib/utils/formatters'

  interface Props {
    data: AppData
    direction: Direction
    foodGroup: string | null
    onFoodGroup: (key: string | null) => void
    selectedCountry: string | null
    selectedProvince: string | null
    onClearSelection: () => void
    traceCount: number | null
    maxHeight: number
  }

  let {
    data, direction, foodGroup, onFoodGroup, selectedCountry, selectedProvince,
    onClearSelection, traceCount, maxHeight,
  }: Props = $props()

  type Bar = { label: string; share: number; color: string; title?: string }

  const cName = (iso: string) => data.places.countries[iso]?.name ?? iso
  const pName = (adm: string) => data.places.provinces[adm]?.name ?? adm
  const group = (k: string) => FOOD_GROUP_BY_KEY[k] ?? { key: k, label: k, color: '#aaaaaa', desc: '' }
  const cap = (s: string) => s.charAt(0).toUpperCase() + s.slice(1)
  const ROUTES = Object.entries(ROUTE_TYPES) as [RouteType, (typeof ROUTE_TYPES)[RouteType]][]

  let dm = $derived(DIRECTION_BY_ID[direction])
  let dirColor = $derived(DIRECTION_COLORS[direction])
  let head = $derived(data.meta.headline[direction])
  let groupRows = $derived(data.foodgroups[direction] ?? [])
  let groupRow = $derived(foodGroup ? (groupRows.find((r) => r.food_group === foodGroup) ?? null) : null)
  let view = $derived(
    selectedCountry && direction !== 'within' ? 'country' : selectedProvince ? 'province' : 'overview',
  )
  let partner = $derived(selectedCountry ? (data.partnerDetail[direction]?.[selectedCountry] ?? null) : null)
  let province = $derived(
    selectedProvince ? ((data.provinces[direction] ?? []).find((p) => p.admin === selectedProvince) ?? null) : null,
  )

  let stats = $derived(
    groupRow
      ? { tonnes: groupRow.tonnes, kcal: groupRow.kcal, partners: groupRow.n_partners,
          eff: groupRow.effective_partners, hhi: groupRow.hhi, top: groupRow.top_partner,
          topShare: groupRow.top_partner_share, routes: groupRow.routes }
      : { tonnes: head.tonnes, kcal: head.kcal, partners: head.partners, eff: head.effective_partners,
          hhi: head.hhi, top: head.top_partner, topShare: head.top_partner_share, routes: head.routes },
  )

  let exposed = $derived(
    (data.commodities[direction] ?? [])
      .filter((r) => !foodGroup || r.food_group === foodGroup)
      .slice()
      .sort((a, b) => b.exposure_index - a.exposure_index)
      .slice(0, 6),
  )
  let maxCal = $derived(Math.max(0.0001, ...groupRows.map((r) => r.calorie_share)))
  let verb = $derived(direction === 'import' ? 'supplies' : 'takes')
  let groupWord = $derived(groupRow ? `${group(groupRow.food_group).label.toLowerCase()} ` : '')
</script>

{#snippet bars(rows: Bar[], max: number)}
  <div class="sp-bars">
    {#each rows as r}
      <div class="sp-bar-row" title={r.title ?? r.label}>
        <div class="sp-bar-label">{r.label}</div>
        <div class="sp-bar-track">
          <div class="sp-bar-fill" style="width: {Math.max(1.5, (r.share / max) * 100)}%; background: {r.color}"></div>
        </div>
        <div class="sp-bar-val">{formatShare(r.share, r.share < 0.1 ? 1 : 0)}</div>
      </div>
    {/each}
  </div>
{/snippet}

{#snippet routeMix(mix: RouteMix | null)}
  {#if mix}
    <div class="sp-section-label">How it travels</div>
    <div class="sp-route-bar">
      {#each ROUTES as [key, rt]}
        {#if mix[key] > 0}
          <span style="width: {mix[key] * 100}%; background: {rt.color}"
            title="{rt.label}: {formatShare(mix[key])} — {rt.desc}"></span>
        {/if}
      {/each}
    </div>
    <div class="sp-route-legend">
      {#each ROUTES as [key, rt]}
        <span title={rt.desc}><i style="background: {rt.color}"></i>{rt.label} <b>{formatShare(mix[key], 0)}</b></span>
      {/each}
    </div>
  {/if}
{/snippet}

<div class="side-panel" style="max-height: {maxHeight}px; --dir: {dirColor}">
  {#if view === 'overview'}
    <div class="sp-badge">Canada · {dm.label}</div>
    <div class="sp-name">
      {groupRow ? `${group(groupRow.food_group).label} ${dm.short}` : cap(dm.flowPhrase)}
    </div>

    {#if direction === 'within'}
      <p class="sp-note">{dm.desc}</p>
      <div class="sp-metrics">
        <div><b>{formatTonnes(stats.tonnes)}</b><span>tonnage</span></div>
        <div><b>{formatKcal(stats.kcal).split(' ')[0]}</b><span>{formatKcal(stats.kcal).split(' ').slice(1).join(' ')}</span></div>
      </div>
      <div class="sp-section-label">Sending provinces</div>
      {@render bars(
        (data.provinces.within ?? []).slice(0, 10).map((p) => ({ label: p.name, share: p.share_of_national, color: dirColor })),
        Math.max(...(data.provinces.within ?? []).map((p) => p.share_of_national), 0.0001),
      )}
    {:else}
      <div class="sp-metrics">
        <div><b>{formatTonnes(stats.tonnes)}</b><span>tonnage</span></div>
        <div><b>{formatKcal(stats.kcal).split(' ')[0]}</b><span>{formatKcal(stats.kcal).split(' ').slice(1).join(' ')}</span></div>
        <div><b>{formatCount(stats.partners)}</b><span>{direction === 'import' ? 'source countries' : 'destinations'}</span></div>
        <div title={METRIC_DESC.effectivePartners}>
          <b style="color: var(--dir)">{formatEffective(stats.eff)}</b><span>effective partners ⓘ</span>
        </div>
      </div>
      <p class="sp-sentence">
        {#if stats.top}
          <strong>{cName(stats.top)}</strong> {verb} <strong style="color: var(--dir)">{formatShare(stats.topShare)}</strong>
          of Canada’s {groupWord}{dm.short}. The trade is {describeHHI(stats.hhi)}
          <span class="sp-muted" title={METRIC_DESC.hhi}>(HHI {stats.hhi?.toFixed(3)})</span>.
        {/if}
      </p>
      {@render routeMix(stats.routes)}

      {#if !groupRow}
        <div class="sp-section-label" style="margin-top: 14px">By food group · click one to filter</div>
        <div class="fg-table" role="table" aria-label="Concentration by food group">
          <div class="fg-row fg-head" role="row">
            <span>Group</span><span>Calories</span><span title={METRIC_DESC.effectivePartners}>Eff. partners</span><span>Largest partner</span>
          </div>
          {#each groupRows as r}
            {@const g = group(r.food_group)}
            <button class="fg-row" role="row" onclick={() => onFoodGroup(r.food_group)}
              title={`Show only ${g.label} — ${g.desc}`}>
              <span class="fg-name"><i style="background: {g.color}"></i>{g.label}</span>
              <span class="fg-bar"><em style="width: {Math.max(2, (r.calorie_share / maxCal) * 100)}%; background: {g.color}"></em><small>{formatShare(r.calorie_share, r.calorie_share < 0.1 ? 1 : 0)}</small></span>
              <span class="fg-num {r.effective_partners !== null && r.effective_partners < 2 ? 'hot' : ''}">{formatEffective(r.effective_partners)}</span>
              <span class="fg-top">{r.top_partner ? `${r.top_partner} ${formatShare(r.top_partner_share, 0)}` : '—'}</span>
            </button>
          {/each}
        </div>
        <p class="sp-muted sp-small">Below 2 effective partners is highlighted: trade that behaves as if it had fewer than two sources.</p>
      {:else}
        <div class="sp-section-label">Largest {direction === 'import' ? 'suppliers' : 'buyers'}</div>
        {@render bars(
          groupRow.top_partners.slice(0, 6).map((p) => ({ label: cName(p.iso3), share: p.share, color: dirColor })),
          groupRow.top_partners[0]?.share ?? 1,
        )}
        <div class="sp-section-label">{dm.regionRole}</div>
        {@render bars(
          groupRow.provinces.slice(0, 6).map((p) => ({ label: pName(p.admin), share: p.share, color: '#c8cdd6' })),
          groupRow.provinces[0]?.share ?? 1,
        )}
        <div class="sp-section-label">Commodities</div>
        {@render bars(
          groupRow.commodities.slice(0, 6).map((c) => ({ label: c.commodity, share: c.share, color: group(groupRow.food_group).color })),
          groupRow.commodities[0]?.share ?? 1,
        )}
        <button class="sp-link" onclick={() => onFoodGroup(null)}>← All food groups</button>
      {/if}

      {#if exposed.length}
        <div class="sp-section-label" style="margin-top: 14px" title={METRIC_DESC.exposureIndex}>
          Most concentrated {groupRow ? '' : 'large '}{dm.short} ⓘ
        </div>
        <div class="exp-list">
          {#each exposed as r}
            <div class="exp-row" title={`${r.commodity}: ${formatShare(r.calorie_share)} of ${dm.short} calories, ${formatEffective(r.effective_partners)} effective partners`}>
              <i style="background: {group(r.food_group).color}"></i>
              <span class="exp-name">{r.commodity}</span>
              <span class="exp-top">{cName(r.top_partner)} {formatShare(r.top_partner_share, 0)}</span>
            </div>
          {/each}
        </div>
      {/if}
    {/if}

  {:else if view === 'country' && selectedCountry}
    <button class="sp-close" onclick={onClearSelection} aria-label="Close">&times;</button>
    <div class="sp-badge">{dm.partnerNoun} · {dm.label}</div>
    <div class="sp-name">{cName(selectedCountry)}</div>
    {#if !partner}
      <p class="sp-note">No recorded {dm.short} {dm.towards} {cName(selectedCountry)} in this data.</p>
    {:else}
      <div class="sp-sub">
        #{partner.rank} of {partner.of} · <strong style="color: var(--dir)">{formatShare(partner.share)}</strong>
        of {dm.flowPhrase} · {formatTonnes(partner.tonnes)}
      </div>
      {#if traceCount !== null}
        <div class="sp-trace">Map shows the {formatCount(traceCount)} segments this trade uses{foodGroup ? ` for ${group(foodGroup).label.toLowerCase()}` : ''}.</div>
      {/if}

      <div class="sp-section-label" title={METRIC_DESC.dependence}>
        {direction === 'import' ? `Share of Canada’s imports it supplies` : `Share of Canada’s exports it takes`} ⓘ
      </div>
      {@render bars(
        partner.dependence.slice(0, 8).map((d) => ({ label: group(d.food_group).label, share: d.share, color: group(d.food_group).color })),
        1,
      )}

      <div class="sp-section-label">What {direction === 'import' ? 'it sends' : 'it buys'}</div>
      {@render bars(
        partner.food_groups.slice(0, 6).map((g) => ({ label: group(g.food_group).label, share: g.share, color: group(g.food_group).color })),
        partner.food_groups[0]?.share ?? 1,
      )}

      <div class="sp-section-label">Top commodities</div>
      {@render bars(
        partner.commodities.slice(0, 6).map((c) => ({ label: c.commodity, share: c.share, color: '#c8cdd6' })),
        partner.commodities[0]?.share ?? 1,
      )}

      <div class="sp-section-label">{dm.regionRole}</div>
      {@render bars(
        partner.provinces.slice(0, 6).map((p) => ({ label: pName(p.admin), share: p.share, color: dirColor })),
        partner.provinces[0]?.share ?? 1,
      )}

      {@render routeMix(partner.routes)}
    {/if}

  {:else if view === 'province' && selectedProvince}
    <button class="sp-close" onclick={onClearSelection} aria-label="Close">&times;</button>
    <div class="sp-badge">{dm.regionRole} · {dm.label}</div>
    <div class="sp-name">{pName(selectedProvince)}</div>
    {#if !province}
      <p class="sp-note">No recorded {dm.short} through {pName(selectedProvince)} in this data.</p>
    {:else}
      <div class="sp-sub">
        <strong style="color: var(--dir)">{formatShare(province.share_of_national)}</strong> of {dm.flowPhrase}
        · {formatTonnes(province.tonnes)}
      </div>
      {#if direction !== 'within'}
        <div class="sp-metrics">
          <div><b>{formatCount(province.n_partners)}</b><span>partner countries</span></div>
          <div title={METRIC_DESC.effectivePartners}>
            <b style="color: var(--dir)">{formatEffective(province.effective_partners)}</b><span>effective partners ⓘ</span>
          </div>
        </div>
        <div class="sp-section-label">Largest partners</div>
        {@render bars(
          province.top_partners.slice(0, 6).map((p) => ({ label: cName(p.iso3), share: p.share, color: dirColor })),
          province.top_partners[0]?.share ?? 1,
        )}
      {/if}
      <div class="sp-section-label">Food groups</div>
      {@render bars(
        province.food_groups.slice(0, 8).map((g) => ({ label: group(g.food_group).label, share: g.share, color: group(g.food_group).color })),
        province.food_groups[0]?.share ?? 1,
      )}
      <div class="sp-section-label">Top commodities</div>
      {@render bars(
        province.commodities.slice(0, 6).map((c) => ({ label: c.commodity, share: c.share, color: '#c8cdd6' })),
        province.commodities[0]?.share ?? 1,
      )}
      {@render routeMix(province.routes)}
      <p class="sp-muted sp-small">
        The Canadian end of each journey — {direction === 'import' ? 'where imports arrive' : 'where the journey begins'} —
        not where the food is eaten or grown.
      </p>
    {/if}
  {/if}
</div>

<style>
  .side-panel {
    position: absolute;
    top: 64px;
    right: 16px;
    z-index: 6;
    width: 370px;
    overflow-y: auto;
    background: rgba(14, 18, 28, 0.94);
    border: 1px solid rgba(255, 255, 255, 0.12);
    border-radius: 10px;
    padding: 14px 14px 12px;
    color: #e0e0e0;
    font-family: system-ui, -apple-system, sans-serif;
    font-size: 13px;
    backdrop-filter: blur(8px);
    box-shadow: 0 8px 32px rgba(0, 0, 0, 0.5);
  }
  .side-panel::-webkit-scrollbar { width: 4px; }
  .side-panel::-webkit-scrollbar-thumb { background: #1e2640; border-radius: 2px; }

  .sp-close {
    position: absolute; top: 8px; right: 10px;
    background: none; border: none; color: #999;
    font-size: 18px; cursor: pointer; line-height: 1; padding: 2px 6px;
  }
  .sp-close:hover { color: #fff; }
  .sp-badge {
    display: inline-block; font-size: 9px; text-transform: uppercase; letter-spacing: 0.6px;
    color: #0a0a0a; background: var(--dir); padding: 1px 6px; border-radius: 3px;
    margin-bottom: 4px; font-weight: 600;
  }
  .sp-name { font-size: 16px; font-weight: 700; color: #fff; line-height: 1.3; padding-right: 22px; }
  .sp-sub { font-size: 12px; color: #9aa3b2; margin: 3px 0 8px; line-height: 1.45; }
  .sp-sub strong { font-variant-numeric: tabular-nums; }
  .sp-note { font-size: 12px; color: #9aa3b2; line-height: 1.5; margin: 8px 0; }
  .sp-sentence { font-size: 12px; color: #9aa3b2; line-height: 1.55; margin: 8px 0 4px; }
  .sp-sentence strong { color: #fff; font-variant-numeric: tabular-nums; }
  .sp-muted { color: #6f7886; }
  .sp-small { font-size: 10.5px; line-height: 1.45; margin: 6px 0 0; }
  .sp-trace {
    font-size: 11px; color: #c8cdd6; line-height: 1.4;
    background: color-mix(in srgb, var(--dir) 12%, transparent);
    border: 1px solid color-mix(in srgb, var(--dir) 35%, transparent);
    border-radius: 6px; padding: 5px 8px; margin: 4px 0 6px;
  }

  .sp-metrics { display: grid; grid-template-columns: 1fr 1fr; gap: 6px; margin: 10px 0 4px; }
  .sp-metrics > div { background: rgba(255, 255, 255, 0.05); border-radius: 6px; padding: 7px 9px; }
  .sp-metrics b { display: block; font-size: 17px; color: #fff; font-variant-numeric: tabular-nums; line-height: 1.2; }
  .sp-metrics span { display: block; font-size: 9.5px; color: #7a8494; text-transform: uppercase; letter-spacing: 0.4px; margin-top: 2px; }

  .sp-section-label {
    font-size: 11px; text-transform: uppercase; letter-spacing: 0.5px;
    color: #6f7886; margin: 12px 0 6px;
  }

  .sp-bars { display: flex; flex-direction: column; gap: 3px; }
  .sp-bar-row { display: grid; grid-template-columns: 118px 1fr 38px; align-items: center; gap: 6px; font-size: 11.5px; }
  .sp-bar-label { color: #c8cdd6; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
  .sp-bar-track { height: 8px; background: rgba(255, 255, 255, 0.06); border-radius: 2px; overflow: hidden; }
  .sp-bar-fill { height: 100%; border-radius: 2px; transition: width 0.2s ease; }
  .sp-bar-val { color: #fff; font-variant-numeric: tabular-nums; text-align: right; }

  .sp-route-bar { display: flex; height: 9px; border-radius: 3px; overflow: hidden; background: rgba(255, 255, 255, 0.06); }
  .sp-route-bar span { height: 100%; }
  .sp-route-legend {
    display: grid; grid-template-columns: 1fr 1fr; gap: 3px 10px; margin-top: 6px;
    font-size: 10.5px; color: #9aa3b2;
  }
  .sp-route-legend i { display: inline-block; width: 8px; height: 8px; border-radius: 2px; margin-right: 5px; vertical-align: -1px; }
  .sp-route-legend b { color: #fff; font-weight: 600; font-variant-numeric: tabular-nums; }

  .fg-table { display: flex; flex-direction: column; }
  .fg-row {
    display: grid; grid-template-columns: 1.35fr 1fr 0.62fr 0.9fr; align-items: center; gap: 6px;
    width: 100%; padding: 4px 4px; background: none; border: none; border-radius: 4px;
    color: #c8cdd6; font-family: inherit; font-size: 11.5px; text-align: left; cursor: pointer;
  }
  .fg-row:hover { background: rgba(255, 255, 255, 0.06); }
  .fg-head { cursor: default; font-size: 9.5px; text-transform: uppercase; letter-spacing: 0.4px; color: #6f7886; }
  .fg-head:hover { background: none; }
  .fg-name { white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
  .fg-name i { display: inline-block; width: 8px; height: 8px; border-radius: 50%; margin-right: 6px; }
  .fg-bar { position: relative; height: 12px; }
  .fg-bar em { position: absolute; left: 0; top: 3px; height: 6px; border-radius: 2px; opacity: 0.85; }
  .fg-bar small { position: absolute; right: 0; top: -1px; font-size: 10px; color: #9aa3b2; font-variant-numeric: tabular-nums; }
  .fg-num { text-align: right; font-variant-numeric: tabular-nums; color: #fff; }
  .fg-num.hot { color: var(--dir); font-weight: 700; }
  .fg-top { text-align: right; font-size: 10.5px; color: #9aa3b2; font-variant-numeric: tabular-nums; white-space: nowrap; }

  .exp-list { display: flex; flex-direction: column; gap: 3px; }
  .exp-row { display: grid; grid-template-columns: 10px 1fr auto; align-items: center; gap: 6px; font-size: 11.5px; }
  .exp-row i { width: 8px; height: 8px; border-radius: 50%; }
  .exp-name { color: #c8cdd6; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
  .exp-top { color: #9aa3b2; font-size: 10.5px; font-variant-numeric: tabular-nums; }

  .sp-link {
    margin-top: 10px; background: none; border: none; padding: 0; cursor: pointer;
    color: #64d2ff; font-family: inherit; font-size: 11.5px;
  }
  .sp-link:hover { text-decoration: underline; }
</style>

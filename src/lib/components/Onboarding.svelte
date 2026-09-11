<script lang="ts">
  import { APP, type Direction } from '$lib/config'

  let { selectedCountry = null, direction }: { selectedCountry?: string | null; direction: Direction } = $props()

  // localStorage can throw (private windows, blocked storage); the app works without it.
  const seen = (k: string) => { try { return !!localStorage.getItem(k) } catch { return false } }
  const mark = (k: string) => { try { localStorage.setItem(k, '1') } catch { /* no storage */ } }

  let showWelcome = $state(!seen(APP.storageKey))
  let clickSeen = $state(seen(APP.hintKeys.clickCountry))
  let exportsSeen = $state(seen(APP.hintKeys.tryExports))

  function dismiss() {
    showWelcome = false
    mark(APP.storageKey)
  }

  // Hint 1 disappears the moment a country is selected; hint 2 once Exports is chosen.
  $effect(() => {
    if (selectedCountry && !clickSeen) { clickSeen = true; mark(APP.hintKeys.clickCountry) }
  })
  $effect(() => {
    if (direction === 'export' && !exportsSeen) { exportsSeen = true; mark(APP.hintKeys.tryExports) }
  })

  let showClickHint = $derived(!showWelcome && !clickSeen)
  let showExportsHint = $derived(!showWelcome && clickSeen && !exportsSeen)
</script>

{#if showWelcome}
  <div class="welcome-overlay" onclick={dismiss} role="presentation">
    <div class="welcome-card" onclick={(e) => e.stopPropagation()} role="dialog" aria-modal="true"
      aria-labelledby="welcome-title" tabindex="-1" onkeydown={(e) => { if (e.key === 'Escape') dismiss() }}>
      <div class="welcome-title" id="welcome-title">{APP.title}</div>
      <div class="welcome-subtitle">Where Canada’s food comes from, and where it goes</div>

      <div class="welcome-body">
        <p>This map follows Canada’s <strong>imports</strong> and <strong>exports</strong> along the roads,
          railways and shipping lanes that carry them, split into <strong>twelve food groups</strong>.</p>
        <div class="welcome-steps">
          <div class="welcome-step"><span class="step-num">1</span><span>Choose <strong>Imports</strong> or <strong>Exports</strong> in the panel on the left</span></div>
          <div class="welcome-step"><span class="step-num">2</span><span>Click any <strong>country</strong> to see what Canada trades with it — and trace its routes</span></div>
          <div class="welcome-step"><span class="step-num">3</span><span>Click a <strong>food group</strong> to see only its routes and partners</span></div>
        </div>
      </div>

      <button class="welcome-btn" onclick={dismiss}>Explore the map</button>
      <div class="welcome-source">Global Food Twin · directional flows for Canada</div>
    </div>
  </div>
{/if}

{#if showClickHint}
  <div class="ctx-hint">Click any country to see what Canada trades with it</div>
{:else if showExportsHint}
  <div class="ctx-hint">Now switch to <strong>Exports</strong> to see where Canada’s food goes</div>
{/if}

<style>
  .welcome-overlay {
    position: fixed; inset: 0; z-index: 100; background: rgba(0, 0, 0, 0.7);
    display: flex; align-items: center; justify-content: center; backdrop-filter: blur(4px);
  }
  .welcome-card {
    background: rgba(14, 18, 28, 0.97); border: 1px solid rgba(255, 255, 255, 0.12); border-radius: 14px;
    padding: 36px 40px 28px; max-width: 480px; width: 90vw; color: #e0e0e0;
    font-family: system-ui, -apple-system, sans-serif; box-shadow: 0 24px 80px rgba(0, 0, 0, 0.6); text-align: center;
    outline: none;
  }
  .welcome-title { font-size: 22px; font-weight: 700; color: #fff; letter-spacing: -0.3px; }
  .welcome-subtitle { font-size: 14px; color: #9aa3b2; margin-top: 4px; }
  .welcome-body { margin: 20px 0 24px; text-align: left; }
  .welcome-body p { font-size: 13px; line-height: 1.6; color: #c8cdd6; margin: 0 0 16px; }
  .welcome-steps { display: flex; flex-direction: column; gap: 10px; }
  .welcome-step { display: flex; align-items: center; gap: 12px; font-size: 13px; color: #c8cdd6; }
  .step-num {
    display: flex; align-items: center; justify-content: center; width: 26px; height: 26px; border-radius: 50%;
    background: rgba(74, 158, 255, 0.15); color: #4A9EFF; font-weight: 700; font-size: 13px; flex-shrink: 0;
  }
  .welcome-btn {
    display: inline-block; background: rgba(74, 158, 255, 0.2); border: 1px solid rgba(74, 158, 255, 0.45);
    color: #7db8ff; font-size: 14px; font-weight: 600; padding: 10px 32px; border-radius: 8px;
    cursor: pointer; font-family: inherit; transition: all 0.15s;
  }
  .welcome-btn:hover { background: rgba(74, 158, 255, 0.3); border-color: rgba(74, 158, 255, 0.65); }
  .welcome-source { margin-top: 16px; font-size: 10px; color: #6f7886; }
  .ctx-hint {
    position: absolute; z-index: 8; top: 98px; left: 50%; transform: translateX(-50%);
    background: rgba(14, 18, 28, 0.9); border: 1px solid rgba(74, 158, 255, 0.35); border-radius: 8px;
    padding: 8px 16px; color: #c8cdd6; font-family: system-ui, -apple-system, sans-serif; font-size: 12px;
    backdrop-filter: blur(6px); pointer-events: none; animation: hintPulse 2s ease-in-out infinite;
  }
  .ctx-hint strong { color: #EE6677; }
  @keyframes hintPulse { 0%, 100% { opacity: 0.9; } 50% { opacity: 0.5; } }
</style>

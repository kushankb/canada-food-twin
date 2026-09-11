/**
 * Formatters — every number the app shows passes through here.
 *
 * Quantities span thirteen orders of magnitude (a 4-tonne edge to 2.1e14 kcal of exports),
 * so each formatter is magnitude-aware and carries its unit. Nothing is formatted inline in
 * a component: that is how "21,695,750.8 t" and "21.7 Mt" end up on the same screen.
 */

const T = ['t', 'kt', 'Mt', 'Gt']
const K = ['kcal', 'thousand kcal', 'million kcal', 'billion kcal', 'trillion kcal']

function scale(v: number, units: string[], step = 1000) {
  let i = 0
  let x = Math.abs(v)
  while (x >= step && i < units.length - 1) {
    x /= step
    i++
  }
  return { value: (v < 0 ? -x : x), unit: units[i] }
}

function sig(x: number) {
  const a = Math.abs(x)
  if (a === 0) return '0'
  if (a < 1) return x.toFixed(2)
  // Keep a decimal up to 100: after scaling, 21.7 Mt is the interesting number and 22 Mt
  // throws away the precision the scaling just bought.
  if (a < 100) return x.toFixed(1)
  return Math.round(x).toLocaleString('en-CA')
}

/** Tonnes, auto-scaled: 4 t · 812 kt · 21.7 Mt */
export function formatTonnes(v: number | null | undefined): string {
  if (v == null || !Number.isFinite(v)) return '—'
  const { value, unit } = scale(v, T)
  return `${sig(value)} ${unit}`
}

/** Calories, auto-scaled: 38.7 trillion kcal */
export function formatKcal(v: number | null | undefined): string {
  if (v == null || !Number.isFinite(v)) return '—'
  const { value, unit } = scale(v, K)
  return `${sig(value)} ${unit}`
}

/**
 * A 0–1 share as a percentage: 0.7464 -> 74.6%. A share that is real but below the display
 * precision reads "<0.1%" (or "<0.01%"), never a false "0.0%".
 */
export function formatShare(v: number | null | undefined, digits = 1): string {
  if (v == null || !Number.isFinite(v)) return '—'
  const pct = v * 100
  const floor = Math.pow(10, -digits)
  if (pct > 0 && pct < floor) return `<${floor.toFixed(digits)}%`
  return `${pct.toFixed(digits)}%`
}

/** HHI to 3 decimals — it is a 0–1 index and rounding to 2 hides real differences. */
export function formatHHI(v: number | null | undefined): string {
  if (v == null || !Number.isFinite(v)) return '—'
  return v.toFixed(3)
}

/** Effective partner count. Deliberately shows the fraction: 1.79 is the point. */
export function formatEffective(v: number | null | undefined): string {
  if (v == null || !Number.isFinite(v)) return '—'
  return v.toFixed(v < 10 ? 2 : 1)
}

/** Plain integer with thousands separators. */
export function formatCount(v: number | null | undefined): string {
  if (v == null || !Number.isFinite(v)) return '—'
  return Math.round(v).toLocaleString('en-CA')
}

/**
 * Compact form for axis ticks, where the unit is already on the axis label.
 * 1_200_000 -> 1.2M
 */
export function formatCompact(v: number | null | undefined): string {
  if (v == null || !Number.isFinite(v)) return '—'
  return new Intl.NumberFormat('en-CA', { notation: 'compact', maximumFractionDigits: 1 }).format(v)
}

/**
 * A concentration reading in words, for captions and screen readers.
 * The thresholds are the conventional competition-policy ones: below 0.15 unconcentrated,
 * 0.15–0.25 moderate, above 0.25 concentrated.
 */
export function describeHHI(hhi: number | null | undefined): string {
  if (hhi == null || !Number.isFinite(hhi)) return 'not measured'
  if (hhi >= 0.6) return 'extremely concentrated'
  if (hhi >= 0.25) return 'highly concentrated'
  if (hhi >= 0.15) return 'moderately concentrated'
  return 'diversified'
}

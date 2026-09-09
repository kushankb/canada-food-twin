import { DIRECTIONS, DIRECTION_COLORS, type Direction } from '../config'

interface Props {
  value: Direction
  onChange: (d: Direction) => void
}

/**
 * The app's primary axis. Every view re-reads from this; it is not a per-chart filter.
 * Domestic sits third and de-emphasised because the source models it only partially.
 */
export function DirectionToggle({ value, onChange }: Props) {
  return (
    <div
      role="radiogroup"
      aria-label="Trade direction"
      className="flex items-center gap-1 rounded-lg border border-[#1e2640] bg-[#0d1120]/80 p-1"
    >
      {DIRECTIONS.map((d) => {
        const active = d.id === value
        return (
          <button
            key={d.id}
            role="radio"
            aria-checked={active}
            aria-label={`${d.label} — food ${d.verb}`}
            title={d.desc}
            onClick={() => onChange(d.id)}
            className={`rounded-md px-3 py-1.5 text-sm font-medium transition-colors duration-200
              ${d.id === 'within' ? 'opacity-80' : ''}
              ${active ? 'text-[#080c16]' : 'text-[#7a8fa6] hover:text-[#e8edf4]'}`}
            style={active ? { background: DIRECTION_COLORS[d.id] } : undefined}
          >
            {d.label}
          </button>
        )
      })}
    </div>
  )
}

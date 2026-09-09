interface Props {
  label: string
  value: string
  unit?: string
  subtitle?: string
  color?: string
  title?: string
}

/** House stat card. Value large and coloured, unit and subtitle carrying the scope. */
export function StatCard({ label, value, unit, subtitle, color = '#e8edf4', title }: Props) {
  return (
    <div
      className="rounded-xl border border-[#1e2640]/70 bg-[#0d1120]/50 p-5 transition-transform
                 duration-200 hover:-translate-y-0.5 hover:shadow-[0_4px_24px_rgba(0,0,0,0.5)]"
      title={title}
    >
      <p className="mb-2 text-xs font-medium uppercase tracking-wider text-[#7a8fa6]">{label}</p>
      <div className="flex items-baseline gap-2">
        <span className="text-3xl font-bold" style={{ color }}>{value}</span>
        {unit && <span className="text-sm text-[#7a8fa6]">{unit}</span>}
      </div>
      {subtitle && <p className="mt-1.5 text-xs text-[#4d5f75]">{subtitle}</p>}
    </div>
  )
}

import { useState } from 'react'
import { APP, VIEWS, DIRECTION_COLORS, type Direction, type ViewId } from './config'
import { useAppData } from './hooks/useData'
import { DirectionToggle } from './components/DirectionToggle'
import { LoadingSpinner } from './components/shared/LoadingSpinner'
import { formatTonnes, formatEffective, formatCount } from './utils/formatters'
import { StatCard } from './components/shared/StatCard'

export default function App() {
  const { data, error, loading } = useAppData()
  const [direction, setDirection] = useState<Direction>('import')
  const [view, setView] = useState<ViewId>('map')

  if (error) {
    return (
      <div className="flex h-full items-center justify-center p-8">
        <div className="max-w-lg rounded-xl border border-[#EE6677]/40 bg-[#0d1120] p-6">
          <h1 className="mb-2 text-lg font-semibold text-[#EE6677]">Could not load the data</h1>
          <p className="text-sm text-[#7a8fa6]">{error.message}</p>
          <p className="mt-3 text-xs text-[#4d5f75]">
            If this is a local checkout, run{' '}
            <code className="text-[#e8edf4]">python3 scripts/build_app_data_v2.py --tag all</code>{' '}
            to regenerate <code className="text-[#e8edf4]">public/data/</code>.
          </p>
        </div>
      </div>
    )
  }

  if (loading || !data) {
    return (
      <div className="flex h-full items-center justify-center">
        <LoadingSpinner label="Loading Canada’s food network — 70,198 segments" />
      </div>
    )
  }

  const head = data.meta.headline[direction]
  const dirMeta = DIRECTION_COLORS[direction]

  return (
    <div className="flex h-full flex-col">
      <header className="flex flex-wrap items-center gap-4 border-b border-[#1e2640] px-6 py-3">
        <div className="mr-auto">
          <h1 className="text-base font-bold tracking-tight">{APP.title}</h1>
          <p className="text-xs text-[#7a8fa6]">{APP.tagline}</p>
        </div>
        <DirectionToggle value={direction} onChange={setDirection} />
      </header>

      <nav className="flex gap-1 border-b border-[#1e2640] px-6" aria-label="Views">
        {VIEWS.map((v) => {
          const active = v.id === view
          const phase2 = 'phase' in v
          return (
            <button
              key={v.id}
              onClick={() => setView(v.id)}
              title={v.question}
              aria-current={active ? 'page' : undefined}
              className={`-mb-px border-b-2 px-3 py-2 text-sm transition-colors duration-200
                ${active
                  ? 'border-current text-[#e8edf4]'
                  : 'border-transparent text-[#7a8fa6] hover:text-[#e8edf4]'}
                ${phase2 ? 'opacity-50' : ''}`}
              style={active ? { color: dirMeta, borderColor: dirMeta } : undefined}
            >
              {v.label}
              {phase2 && <span className="ml-1.5 text-[10px] uppercase tracking-wide">soon</span>}
            </button>
          )
        })}
      </nav>

      <main className="flex-1 overflow-auto p-6">
        <div className="mb-6 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          <StatCard
            label={`${direction === 'within' ? 'Domestic' : direction} tonnage`}
            value={formatTonnes(head.tonnes)}
            subtitle="Full network, no threshold"
            color={dirMeta}
          />
          <StatCard
            label="Partner countries"
            value={formatCount(head.partners)}
            subtitle={direction === 'import' ? 'Countries of production' : 'Countries of destination'}
          />
          <StatCard
            label="Effective partners"
            value={formatEffective(head.effective_partners)}
            subtitle="1 / HHI — sourcing breadth, not substitutability"
            color={dirMeta}
          />
          <StatCard
            label="Commodities"
            value={formatCount(head.commodities)}
            subtitle={`across ${head.food_groups} food groups`}
          />
        </div>

        <div className="rounded-xl border border-dashed border-[#1e2640] p-10 text-center">
          <p className="text-sm text-[#7a8fa6]">
            <span className="font-medium text-[#e8edf4]">{VIEWS.find((v) => v.id === view)?.label}</span>{' '}
            — {VIEWS.find((v) => v.id === view)?.question}
          </p>
          <p className="mt-2 text-xs text-[#4d5f75]">
            Shell only. {formatCount(data.network.count)} edges decoded and ready.
          </p>
        </div>
      </main>
    </div>
  )
}

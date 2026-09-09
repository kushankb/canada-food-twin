export function LoadingSpinner({ label = 'Loading' }: { label?: string }) {
  return (
    <div className="flex flex-col items-center justify-center gap-3 p-8" role="status" aria-live="polite">
      <div
        className="h-8 w-8 animate-spin rounded-full border-2 border-[#1e2640] border-t-[#4A9EFF]"
        aria-hidden="true"
      />
      <p className="text-sm text-[#7a8fa6]">{label}</p>
    </div>
  )
}

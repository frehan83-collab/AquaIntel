export default function WelfareLoading() {
  return (
    <div className="space-y-6 animate-pulse">
      {/* Header skeleton */}
      <div className="flex items-center gap-3">
        <div className="w-7 h-7 rounded bg-slate-200 dark:bg-slate-700" />
        <div className="h-7 w-64 rounded bg-slate-200 dark:bg-slate-700" />
      </div>
      <div className="h-4 w-96 rounded bg-slate-200 dark:bg-slate-700" />

      {/* Search skeleton */}
      <div className="rounded-xl border border-slate-200 dark:border-white/[0.06] bg-white/60 dark:bg-white/[0.02] p-4">
        <div className="h-10 w-full max-w-lg rounded-lg bg-slate-200 dark:bg-slate-700" />
      </div>

      {/* Score cards skeleton */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        {[...Array(3)].map((_, i) => (
          <div key={i} className="rounded-xl border border-slate-200 dark:border-white/[0.06] bg-white/60 dark:bg-white/[0.02] p-8 flex flex-col items-center gap-4">
            <div className="h-3 w-20 rounded bg-slate-200 dark:bg-slate-700" />
            <div className="w-32 h-32 rounded-full bg-slate-200 dark:bg-slate-700" />
          </div>
        ))}
      </div>

      {/* Component bars skeleton */}
      <div className="rounded-xl border border-slate-200 dark:border-white/[0.06] bg-white/60 dark:bg-white/[0.02] p-6 space-y-4">
        <div className="h-4 w-40 rounded bg-slate-200 dark:bg-slate-700" />
        {[...Array(5)].map((_, i) => (
          <div key={i} className="flex items-center gap-3">
            <div className="w-4 h-4 rounded bg-slate-200 dark:bg-slate-700" />
            <div className="flex-1 space-y-1">
              <div className="h-3 w-24 rounded bg-slate-200 dark:bg-slate-700" />
              <div className="h-2 rounded-full bg-slate-200 dark:bg-slate-700" />
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

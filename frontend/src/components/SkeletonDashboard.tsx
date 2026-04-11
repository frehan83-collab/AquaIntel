import SkeletonCard from "@/components/SkeletonCard";

export default function SkeletonDashboard() {
  return (
    <div className="space-y-6">
      {/* Hero area: 1 wide KPI + 3 smaller KPIs */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <SkeletonCard variant="kpi" className="col-span-2 md:col-span-1 p-5" />
        <SkeletonCard variant="kpi" className="p-5" />
        <SkeletonCard variant="kpi" className="p-5" />
        <SkeletonCard variant="kpi" className="p-5" />
      </div>

      {/* Chart row */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        <SkeletonCard variant="chart" className="h-56" />
        <SkeletonCard variant="chart" className="h-56" />
      </div>

      {/* Signals / table section */}
      <SkeletonCard variant="table" />
    </div>
  );
}

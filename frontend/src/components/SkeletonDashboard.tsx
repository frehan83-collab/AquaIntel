import SkeletonCard from "@/components/SkeletonCard";

export default function SkeletonDashboard() {
  return (
    <div className="space-y-6">
      {/* KPI row */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        {[0, 1, 2, 3].map((i) => (
          <SkeletonCard key={i} lines={1} hasHeader={true} className="p-4" />
        ))}
      </div>
      {/* Data panels */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        <SkeletonCard lines={5} />
        <SkeletonCard lines={5} />
      </div>
    </div>
  );
}

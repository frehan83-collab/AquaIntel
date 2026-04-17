import KPISkeleton from "@/components/KPISkeleton";
import ChartSkeleton from "@/components/ChartSkeleton";
import TableSkeleton from "@/components/TableSkeleton";

export default function Loading() {
  return (
    <div className="space-y-6">
      <KPISkeleton count={4} />
      <ChartSkeleton />
      <TableSkeleton />
    </div>
  );
}

import KPISkeleton from "@/components/KPISkeleton";
import TableSkeleton from "@/components/TableSkeleton";

export default function Loading() {
  return (
    <div className="space-y-6">
      <KPISkeleton count={4} />
      <TableSkeleton rows={7} />
    </div>
  );
}

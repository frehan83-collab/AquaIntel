import TableSkeleton from "@/components/TableSkeleton";

export default function Loading() {
  return (
    <div className="space-y-6">
      <TableSkeleton rows={30} columns={6} />
    </div>
  );
}

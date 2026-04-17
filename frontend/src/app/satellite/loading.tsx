import MapSkeleton from "@/components/MapSkeleton";
import ChartSkeleton from "@/components/ChartSkeleton";

export default function Loading() {
  return (
    <div className="space-y-6">
      <MapSkeleton />
      <ChartSkeleton />
    </div>
  );
}

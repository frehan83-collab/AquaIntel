import MapSkeleton from "@/components/MapSkeleton";
import KPISkeleton from "@/components/KPISkeleton";

export default function Loading() {
  return (
    <div className="space-y-6">
      <MapSkeleton />
      <KPISkeleton count={3} />
    </div>
  );
}

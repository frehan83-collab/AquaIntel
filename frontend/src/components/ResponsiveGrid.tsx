"use client";

interface Props {
  children: React.ReactNode;
  cols?: { sm?: number; md?: number; lg?: number; xl?: number };
  gap?: number;
  className?: string;
}

// Tailwind requires full class names at build time — dynamic interpolation breaks purging.
// Pre-map every value we might use so Tailwind can see the full string.
const colMap: Record<number, string> = {
  1: "grid-cols-1",
  2: "grid-cols-2",
  3: "grid-cols-3",
  4: "grid-cols-4",
  5: "grid-cols-5",
  6: "grid-cols-6",
};
const mdColMap: Record<number, string> = {
  1: "md:grid-cols-1",
  2: "md:grid-cols-2",
  3: "md:grid-cols-3",
  4: "md:grid-cols-4",
  5: "md:grid-cols-5",
  6: "md:grid-cols-6",
};
const lgColMap: Record<number, string> = {
  1: "lg:grid-cols-1",
  2: "lg:grid-cols-2",
  3: "lg:grid-cols-3",
  4: "lg:grid-cols-4",
  5: "lg:grid-cols-5",
  6: "lg:grid-cols-6",
};
const xlColMap: Record<number, string> = {
  1: "xl:grid-cols-1",
  2: "xl:grid-cols-2",
  3: "xl:grid-cols-3",
  4: "xl:grid-cols-4",
  5: "xl:grid-cols-5",
  6: "xl:grid-cols-6",
};
const gapMap: Record<number, string> = {
  1: "gap-1",
  2: "gap-2",
  3: "gap-3",
  4: "gap-4",
  5: "gap-5",
  6: "gap-6",
  8: "gap-8",
};

export default function ResponsiveGrid({
  children,
  cols = { sm: 1, md: 2, lg: 3, xl: 4 },
  gap = 4,
  className = "",
}: Props) {
  const sm = colMap[cols.sm || 1] || "grid-cols-1";
  const md = mdColMap[cols.md || 2] || "md:grid-cols-2";
  const lg = lgColMap[cols.lg || 3] || "lg:grid-cols-3";
  const xl = xlColMap[cols.xl || 4] || "xl:grid-cols-4";
  const g = gapMap[gap] || "gap-4";

  return (
    <div className={`grid ${sm} ${md} ${lg} ${xl} ${g} ${className}`}>
      {children}
    </div>
  );
}

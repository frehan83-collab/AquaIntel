"use client";
import { motion } from "framer-motion";
import { cn } from "@/lib/utils";
import { ReactNode } from "react";

interface BentoItem {
  id: string;
  /** Columns to span (default 1) */
  colSpan?: 1 | 2 | 3;
  /** Rows to span (default 1) */
  rowSpan?: 1 | 2;
  children: ReactNode;
}

interface BentoGridProps {
  items: BentoItem[];
  /** Number of columns on large screens (default 4) */
  columns?: number;
  /** Gap in px (default 16) */
  gap?: number;
  className?: string;
}

const stagger = {
  hidden: {},
  visible: {
    transition: { staggerChildren: 0.06 },
  },
};

const itemVariant = {
  hidden: { opacity: 0, y: 12, scale: 0.98 },
  visible: {
    opacity: 1,
    y: 0,
    scale: 1,
    transition: { duration: 0.4, ease: [0.25, 0.46, 0.45, 0.94] as const },
  },
};

/**
 * Variable-size CSS Grid layout for dashboard widgets.
 * Supports 1-3 column spans and 1-2 row spans per item.
 * Responsive: lg uses configured columns, md=2, sm=1.
 */
export function BentoGrid({ items, columns = 4, gap = 16, className }: BentoGridProps) {
  return (
    <motion.div
      variants={stagger}
      initial="hidden"
      animate="visible"
      className={cn("grid w-full", className)}
      style={{
        gap: `${gap}px`,
        gridTemplateColumns: `repeat(${columns}, 1fr)`,
      }}
    >
      {items.map((item) => (
        <motion.div
          key={item.id}
          variants={itemVariant}
          className={cn(
            "relative overflow-hidden",
            "rounded-2xl",
            "bg-[var(--bg-card)] dark:bg-gradient-to-br dark:from-fjord-surface/60 dark:to-fjord-midwater/40",
            "border border-slate-200 dark:border-white/[0.08]",
            "shadow-xs dark:shadow-[0_8px_32px_rgba(0,0,0,0.3),inset_0_1px_0_rgba(255,255,255,0.03)]",
            "p-5",
            "transition-all duration-300",
            "hover:border-salmon/30 dark:hover:border-salmon/[0.15]",
            "hover:shadow-md hover:-translate-y-0.5",
            // Responsive: collapse spans on small screens
            item.colSpan === 3
              ? "col-span-1 md:col-span-2 lg:col-span-3"
              : item.colSpan === 2
              ? "col-span-1 md:col-span-2"
              : "col-span-1",
            item.rowSpan === 2 ? "row-span-1 md:row-span-2" : "row-span-1",
          )}
        >
          {/* Subtle accent bar */}
          <div className="absolute top-0 left-0 bottom-0 w-[2px] bg-gradient-to-b from-ocean-500/50 via-ocean-400/20 to-transparent" />
          <div className="relative z-10">{item.children}</div>
        </motion.div>
      ))}

      {/* Responsive overrides via inline style media queries */}
      <style jsx>{`
        @media (max-width: 1023px) {
          div:first-child {
            grid-template-columns: repeat(2, 1fr) !important;
          }
        }
        @media (max-width: 639px) {
          div:first-child {
            grid-template-columns: 1fr !important;
          }
        }
      `}</style>
    </motion.div>
  );
}

export default BentoGrid;

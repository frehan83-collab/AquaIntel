"use client";
import { motion, AnimatePresence } from "framer-motion";
import { X, ChevronUp, ChevronDown, RotateCcw, Settings2, Eye, EyeOff, GripVertical } from "lucide-react";
import type { WidgetConfig } from "@/lib/useDashboardLayout";

interface Props {
  open: boolean;
  onClose: () => void;
  widgets: WidgetConfig[];
  moveWidget: (id: string, direction: "up" | "down") => void;
  toggleWidget: (id: string) => void;
  resetLayout: () => void;
}

export default function DashboardCustomizePanel({
  open,
  onClose,
  widgets,
  moveWidget,
  toggleWidget,
  resetLayout,
}: Props) {
  return (
    <AnimatePresence>
      {open && (
        <>
          {/* Backdrop */}
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            className="fixed inset-0 bg-black/40 backdrop-blur-xs z-50"
            onClick={onClose}
          />

          {/* Panel — slides in from right */}
          <motion.div
            initial={{ x: "100%" }}
            animate={{ x: 0 }}
            exit={{ x: "100%" }}
            transition={{ type: "spring", damping: 26, stiffness: 300 }}
            className="fixed top-0 right-0 h-full w-[340px] max-w-[90vw] z-50
              bg-[var(--glass-bg,rgba(15,23,42,0.92))] backdrop-blur-xl
              border-l border-white/[0.08] shadow-2xl
              flex flex-col"
          >
            {/* Header */}
            <div className="flex items-center justify-between px-5 py-4 border-b border-white/[0.08]">
              <div className="flex items-center gap-2">
                <Settings2 className="w-4 h-4 text-ocean-400" />
                <h2 className="text-sm font-semibold text-[var(--text-primary)]">
                  Customize Dashboard
                </h2>
              </div>
              <button
                onClick={onClose}
                className="p-1.5 rounded-lg hover:bg-white/[0.06] transition-colors"
                aria-label="Close panel"
              >
                <X className="w-4 h-4 text-[var(--text-secondary)]" />
              </button>
            </div>

            {/* Widget list */}
            <div className="flex-1 overflow-y-auto px-4 py-3 space-y-1.5">
              <p className="text-[10px] text-[var(--text-secondary)] uppercase tracking-wider mb-2 px-1">
                Drag order &middot; Toggle visibility
              </p>
              {widgets.map((widget, index) => (
                <div
                  key={widget.id}
                  className={`flex items-center gap-2 px-3 py-2.5 rounded-xl border transition-colors ${
                    widget.visible
                      ? "bg-white/[0.03] border-white/[0.08] hover:border-white/[0.12]"
                      : "bg-white/[0.01] border-white/[0.04] opacity-50"
                  }`}
                >
                  {/* Grip icon */}
                  <GripVertical className="w-3.5 h-3.5 text-[var(--text-secondary)] opacity-40 flex-shrink-0" />

                  {/* Label */}
                  <span className={`flex-1 text-xs font-medium ${
                    widget.visible ? "text-[var(--text-primary)]" : "text-[var(--text-secondary)]"
                  }`}>
                    {widget.label}
                  </span>

                  {/* Up / Down arrows */}
                  <div className="flex items-center gap-0.5">
                    <button
                      onClick={() => moveWidget(widget.id, "up")}
                      disabled={index === 0}
                      className="p-1 rounded-md hover:bg-white/[0.06] disabled:opacity-20 disabled:cursor-not-allowed transition-colors"
                      aria-label={`Move ${widget.label} up`}
                    >
                      <ChevronUp className="w-3.5 h-3.5 text-[var(--text-secondary)]" />
                    </button>
                    <button
                      onClick={() => moveWidget(widget.id, "down")}
                      disabled={index === widgets.length - 1}
                      className="p-1 rounded-md hover:bg-white/[0.06] disabled:opacity-20 disabled:cursor-not-allowed transition-colors"
                      aria-label={`Move ${widget.label} down`}
                    >
                      <ChevronDown className="w-3.5 h-3.5 text-[var(--text-secondary)]" />
                    </button>
                  </div>

                  {/* Toggle switch */}
                  <button
                    onClick={() => toggleWidget(widget.id)}
                    className={`relative w-9 h-5 rounded-full transition-colors flex-shrink-0 ${
                      widget.visible
                        ? "bg-ocean-500/60"
                        : "bg-white/[0.08]"
                    }`}
                    aria-label={`${widget.visible ? "Hide" : "Show"} ${widget.label}`}
                  >
                    <motion.div
                      className="absolute top-0.5 w-4 h-4 rounded-full bg-white shadow-xs flex items-center justify-center"
                      animate={{ left: widget.visible ? 18 : 2 }}
                      transition={{ type: "spring", stiffness: 500, damping: 30 }}
                    >
                      {widget.visible ? (
                        <Eye className="w-2.5 h-2.5 text-ocean-600" />
                      ) : (
                        <EyeOff className="w-2.5 h-2.5 text-gray-400" />
                      )}
                    </motion.div>
                  </button>
                </div>
              ))}
            </div>

            {/* Footer */}
            <div className="px-5 py-4 border-t border-white/[0.08]">
              <button
                onClick={resetLayout}
                className="flex items-center justify-center gap-2 w-full px-4 py-2.5 rounded-xl
                  text-xs font-medium text-[var(--text-secondary)]
                  bg-white/[0.03] border border-white/[0.08]
                  hover:bg-white/[0.06] hover:text-[var(--text-primary)] transition-colors"
              >
                <RotateCcw className="w-3.5 h-3.5" />
                Reset to Default
              </button>
              <p className="text-[9px] text-[var(--text-secondary)] text-center mt-2 opacity-60">
                Changes are saved automatically
              </p>
            </div>
          </motion.div>
        </>
      )}
    </AnimatePresence>
  );
}

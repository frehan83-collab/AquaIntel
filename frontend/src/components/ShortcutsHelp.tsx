"use client";
import { useEffect, useRef } from "react";
import { X } from "lucide-react";
import { motion, AnimatePresence } from "framer-motion";

interface ShortcutsHelpProps {
  open: boolean;
  onClose: () => void;
}

const SECTIONS = [
  {
    title: "Search",
    shortcuts: [
      { keys: ["Ctrl", "K"], description: "Focus sidebar search" },
    ],
  },
  {
    title: "Navigation (press g then a letter)",
    shortcuts: [
      { keys: ["g", "d"], description: "Go to Dashboard" },
      { keys: ["g", "m"], description: "Go to Market Terminal" },
      { keys: ["g", "s"], description: "Go to Signals" },
      { keys: ["g", "f"], description: "Go to Farmer Daily" },
      { keys: ["g", "p"], description: "Go to Portfolio" },
      { keys: ["g", "b"], description: "Go to Morning Brief" },
      { keys: ["g", "t"], description: "Go to Trader Intel" },
      { keys: ["g", "i"], description: "Go to Investor Intel" },
    ],
  },
  {
    title: "General",
    shortcuts: [
      { keys: ["Ctrl", "/"], description: "Toggle this help panel" },
      { keys: ["Esc"], description: "Close modal / dropdown" },
    ],
  },
];

function Kbd({ children }: { children: string }) {
  return (
    <kbd className="inline-flex items-center justify-center min-w-[24px] h-6 px-1.5 rounded bg-white/[0.08] border border-white/[0.12] text-[11px] font-mono text-slate-300 shadow-[0_1px_2px_rgba(0,0,0,0.3)]">
      {children}
    </kbd>
  );
}

export default function ShortcutsHelp({ open, onClose }: ShortcutsHelpProps) {
  const panelRef = useRef<HTMLDivElement>(null);

  // Close on click outside
  useEffect(() => {
    if (!open) return;
    function handleClick(e: MouseEvent) {
      if (panelRef.current && !panelRef.current.contains(e.target as Node)) {
        onClose();
      }
    }
    // Delay to avoid closing immediately from the triggering click
    const timer = setTimeout(() => {
      document.addEventListener("mousedown", handleClick);
    }, 50);
    return () => {
      clearTimeout(timer);
      document.removeEventListener("mousedown", handleClick);
    };
  }, [open, onClose]);

  return (
    <AnimatePresence>
      {open && (
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          transition={{ duration: 0.15 }}
          className="fixed inset-0 z-[200] flex items-center justify-center bg-black/50 backdrop-blur-xs"
        >
          <motion.div
            ref={panelRef}
            initial={{ opacity: 0, scale: 0.95, y: 8 }}
            animate={{ opacity: 1, scale: 1, y: 0 }}
            exit={{ opacity: 0, scale: 0.95, y: 8 }}
            transition={{ duration: 0.15 }}
            className="w-full max-w-md mx-4 rounded-xl bg-slate-900/95 backdrop-blur-xl border border-white/[0.08] shadow-2xl overflow-hidden"
          >
            {/* Header */}
            <div className="flex items-center justify-between px-5 py-4 border-b border-white/[0.06]">
              <h2 className="text-sm font-semibold text-slate-200">Keyboard Shortcuts</h2>
              <button
                onClick={onClose}
                className="p-1 rounded-md text-slate-400 hover:text-slate-200 hover:bg-white/[0.06] transition-colors"
                aria-label="Close shortcuts help"
              >
                <X className="w-4 h-4" />
              </button>
            </div>

            {/* Content */}
            <div className="px-5 py-4 space-y-5 max-h-[60vh] overflow-y-auto">
              {SECTIONS.map((section) => (
                <div key={section.title}>
                  <h3 className="text-[10px] uppercase tracking-widest text-salmon/60 font-semibold mb-2">
                    {section.title}
                  </h3>
                  <div className="space-y-2">
                    {section.shortcuts.map((shortcut) => (
                      <div
                        key={shortcut.description}
                        className="flex items-center justify-between"
                      >
                        <span className="text-[13px] text-slate-300">{shortcut.description}</span>
                        <div className="flex items-center gap-1">
                          {shortcut.keys.map((key, i) => (
                            <span key={i} className="flex items-center gap-1">
                              {i > 0 && (
                                <span className="text-[10px] text-slate-500">+</span>
                              )}
                              <Kbd>{key}</Kbd>
                            </span>
                          ))}
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              ))}
            </div>

            {/* Footer */}
            <div className="px-5 py-3 border-t border-white/[0.06] bg-white/[0.02]">
              <p className="text-[11px] text-slate-500 text-center">
                Press <Kbd>Ctrl</Kbd> <span className="text-slate-500">+</span> <Kbd>/</Kbd> to toggle this panel
              </p>
            </div>
          </motion.div>
        </motion.div>
      )}
    </AnimatePresence>
  );
}

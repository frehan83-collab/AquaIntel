"use client";
import { useState, useEffect, useCallback, createContext, useContext } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { X, AlertTriangle, CheckCircle, Info, Zap } from "lucide-react";

/* eslint-disable @typescript-eslint/no-explicit-any */

type ToastType = "info" | "success" | "warning" | "error" | "alert";

interface Toast {
  id: string;
  type: ToastType;
  title: string;
  message?: string;
  duration?: number;
}

interface ToastContextType {
  addToast: (toast: Omit<Toast, "id">) => void;
}

const ToastContext = createContext<ToastContextType>({ addToast: () => {} });

export function useToast() {
  return useContext(ToastContext);
}

const ICONS: Record<ToastType, any> = {
  info: Info,
  success: CheckCircle,
  warning: AlertTriangle,
  error: Zap,
  alert: AlertTriangle,
};

const STYLES: Record<ToastType, string> = {
  info: "border-ocean-500/30 bg-ocean-500/[0.08]",
  success: "border-emerald-500/30 bg-emerald-500/[0.08]",
  warning: "border-amber-500/30 bg-amber-500/[0.08]",
  error: "border-rose-500/30 bg-rose-500/[0.08]",
  alert: "border-rose-500/30 bg-rose-500/[0.08]",
};

const ICON_COLORS: Record<ToastType, string> = {
  info: "text-ocean-400",
  success: "text-emerald-400",
  warning: "text-amber-400",
  error: "text-rose-400",
  alert: "text-rose-400",
};

export function ToastProvider({ children }: { children: React.ReactNode }) {
  const [toasts, setToasts] = useState<Toast[]>([]);

  const addToast = useCallback((toast: Omit<Toast, "id">) => {
    const id = `toast-${Date.now()}-${Math.random().toString(36).slice(2, 6)}`;
    setToasts((prev) => [...prev.slice(-4), { ...toast, id }]); // Keep max 5
  }, []);

  const removeToast = useCallback((id: string) => {
    setToasts((prev) => prev.filter((t) => t.id !== id));
  }, []);

  return (
    <ToastContext.Provider value={{ addToast }}>
      {children}

      {/* Toast Container */}
      <div className="fixed top-4 right-4 z-[100] flex flex-col gap-2 pointer-events-none" style={{ maxWidth: 380 }}>
        <AnimatePresence>
          {toasts.map((toast) => (
            <ToastItem key={toast.id} toast={toast} onDismiss={removeToast} />
          ))}
        </AnimatePresence>
      </div>
    </ToastContext.Provider>
  );
}

function ToastItem({ toast, onDismiss }: { toast: Toast; onDismiss: (id: string) => void }) {
  const Icon = ICONS[toast.type] || Info;
  const duration = toast.duration ?? 5000;

  useEffect(() => {
    if (duration > 0) {
      const timer = setTimeout(() => onDismiss(toast.id), duration);
      return () => clearTimeout(timer);
    }
  }, [toast.id, duration, onDismiss]);

  return (
    <motion.div
      initial={{ opacity: 0, x: 50, scale: 0.95 }}
      animate={{ opacity: 1, x: 0, scale: 1 }}
      exit={{ opacity: 0, x: 50, scale: 0.95 }}
      transition={{ duration: 0.25, ease: "easeOut" }}
      className={`pointer-events-auto flex items-start gap-3 px-4 py-3 rounded-xl border backdrop-blur-xl shadow-lg ${STYLES[toast.type]}`}
    >
      <Icon className={`w-4 h-4 flex-shrink-0 mt-0.5 ${ICON_COLORS[toast.type]}`} />
      <div className="flex-1 min-w-0">
        <p className="text-sm font-semibold text-[var(--text-primary)]">{toast.title}</p>
        {toast.message && (
          <p className="text-xs text-[var(--text-secondary)] mt-0.5 line-clamp-2">{toast.message}</p>
        )}
      </div>
      <button
        onClick={() => onDismiss(toast.id)}
        className="flex-shrink-0 p-0.5 rounded-md text-[var(--text-secondary)] hover:text-[var(--text-primary)] transition-colors"
      >
        <X className="w-3.5 h-3.5" />
      </button>
    </motion.div>
  );
}

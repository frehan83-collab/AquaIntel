"use client";
import { useState, useEffect, useRef } from "react";
import { WifiOff, RefreshCw } from "lucide-react";
import { motion, AnimatePresence } from "framer-motion";

type Status = "online" | "offline" | "api-down" | "reconnecting";

export default function OfflineIndicator() {
  const [status, setStatus] = useState<Status>("online");
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null);

  useEffect(() => {
    const goOffline = () => setStatus("offline");
    const goOnline = () => {
      setStatus("reconnecting");
      // Verify API is actually reachable
      checkApi();
    };
    window.addEventListener("offline", goOffline);
    window.addEventListener("online", goOnline);
    if (!navigator.onLine) setStatus("offline");

    // Periodic API health check (every 30s when degraded)
    function checkApi() {
      const base = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
      fetch(`${base}/api/health`, { signal: AbortSignal.timeout(5000) })
        .then((r) => {
          if (r.ok) setStatus("online");
          else setStatus("api-down");
        })
        .catch(() => {
          if (navigator.onLine) setStatus("api-down");
          else setStatus("offline");
        });
    }

    // Only poll when degraded
    intervalRef.current = setInterval(() => {
      if (status !== "online") checkApi();
    }, 30_000);

    return () => {
      window.removeEventListener("offline", goOffline);
      window.removeEventListener("online", goOnline);
      if (intervalRef.current) clearInterval(intervalRef.current);
    };
  }, [status]);

  const messages: Record<Status, { icon: React.ReactNode; text: string; color: string }> = {
    online: { icon: null, text: "", color: "" },
    offline: {
      icon: <WifiOff className="w-3.5 h-3.5" />,
      text: "Offline — showing cached data",
      color: "bg-amber-500/90",
    },
    "api-down": {
      icon: <WifiOff className="w-3.5 h-3.5" />,
      text: "API unreachable — some data may be stale",
      color: "bg-rose-500/90",
    },
    reconnecting: {
      icon: <RefreshCw className="w-3.5 h-3.5 animate-spin" />,
      text: "Reconnecting...",
      color: "bg-ocean-500/90",
    },
  };

  const msg = messages[status];

  return (
    <AnimatePresence>
      {status !== "online" && (
        <motion.div
          initial={{ opacity: 0, y: -20 }}
          animate={{ opacity: 1, y: 0 }}
          exit={{ opacity: 0, y: -20 }}
          className={`fixed top-0 left-0 right-0 z-[200] flex items-center justify-center gap-2 py-2 ${msg.color} backdrop-blur text-white text-xs font-semibold`}
        >
          {msg.icon}
          {msg.text}
        </motion.div>
      )}
    </AnimatePresence>
  );
}

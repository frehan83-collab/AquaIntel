"use client";
import { useEffect, useState, useCallback, useRef } from "react";
import { useRouter } from "next/navigation";

export function useKeyboardShortcuts() {
  const router = useRouter();
  const [showHelp, setShowHelp] = useState(false);
  const pendingG = useRef(false);
  const gTimer = useRef<ReturnType<typeof setTimeout> | null>(null);

  const isInputFocused = useCallback(() => {
    const el = document.activeElement;
    if (!el) return false;
    const tag = el.tagName.toLowerCase();
    if (tag === "input" || tag === "textarea" || tag === "select") return true;
    if ((el as HTMLElement).isContentEditable) return true;
    return false;
  }, []);

  useEffect(() => {
    function handleKeyDown(e: KeyboardEvent) {
      const mod = e.metaKey || e.ctrlKey;

      // Cmd+K / Ctrl+K -> focus sidebar search
      if (mod && e.key === "k") {
        e.preventDefault();
        window.dispatchEvent(new CustomEvent("focus-sidebar-search"));
        return;
      }

      // Cmd+/ / Ctrl+/ -> show shortcuts help
      if (mod && e.key === "/") {
        e.preventDefault();
        setShowHelp((v) => !v);
        return;
      }

      // Escape -> close help modal (and dispatch generic close event)
      if (e.key === "Escape") {
        if (showHelp) {
          setShowHelp(false);
          return;
        }
        window.dispatchEvent(new CustomEvent("close-modal"));
        return;
      }

      // Skip vim-style shortcuts when typing in inputs
      if (isInputFocused()) return;

      // Vim-style "g then X" navigation
      if (e.key === "g" && !mod && !e.altKey) {
        if (!pendingG.current) {
          pendingG.current = true;
          if (gTimer.current) clearTimeout(gTimer.current);
          gTimer.current = setTimeout(() => {
            pendingG.current = false;
          }, 800);
          return;
        }
      }

      if (pendingG.current) {
        pendingG.current = false;
        if (gTimer.current) clearTimeout(gTimer.current);

        const routes: Record<string, string> = {
          d: "/",
          m: "/market",
          s: "/signals",
          f: "/farmer-daily",
          p: "/portfolio",
          b: "/brief",
          t: "/trader",
          i: "/investor",
        };

        const route = routes[e.key];
        if (route) {
          e.preventDefault();
          router.push(route);
          return;
        }
      }
    }

    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [router, showHelp, isInputFocused]);

  return { showHelp, setShowHelp };
}

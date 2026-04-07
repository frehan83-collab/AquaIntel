"use client";
import { useKeyboardShortcuts } from "@/lib/useKeyboardShortcuts";
import ShortcutsHelp from "@/components/ShortcutsHelp";

export default function KeyboardShortcuts() {
  const { showHelp, setShowHelp } = useKeyboardShortcuts();
  return <ShortcutsHelp open={showHelp} onClose={() => setShowHelp(false)} />;
}

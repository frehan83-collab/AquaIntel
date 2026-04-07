"use client";
import { Loader2 } from "lucide-react";

interface Props { message?: string; }

export default function PageLoader({ message = "Loading intelligence..." }: Props) {
  return (
    <div className="flex flex-col items-center justify-center py-24">
      <Loader2 className="w-8 h-8 animate-spin text-ocean-400 mb-3" />
      <p className="text-sm text-[var(--text-secondary)]">{message}</p>
    </div>
  );
}

"use client";
import { Inbox } from "lucide-react";
import { useTranslation } from "@/lib/i18n";

interface Props {
  title?: string;
  message?: string;
  icon?: React.ReactNode;
}

export default function EmptyState({
  title,
  message,
  icon,
}: Props) {
  const { t } = useTranslation();
  const resolvedTitle = title ?? t("empty.title");
  const resolvedMessage = message ?? t("empty.message");
  return (
    <div className="flex flex-col items-center justify-center py-16 opacity-60">
      <div className="w-12 h-12 rounded-2xl bg-white/[0.04] border border-white/[0.06] flex items-center justify-center mb-3">
        {icon || <Inbox className="w-6 h-6 text-[var(--text-secondary)]" />}
      </div>
      <h3 className="text-sm font-medium text-[var(--text-primary)] mb-1">{resolvedTitle}</h3>
      <p className="text-xs text-[var(--text-secondary)] text-center max-w-xs">{resolvedMessage}</p>
    </div>
  );
}

"use client";

import { useState, useMemo, useCallback } from "react";
import { ChevronUp, ChevronDown, ChevronLeft, ChevronRight, Search, Download, X } from "lucide-react";
import { exportToCSV, exportToExcel } from "@/lib/export";
import { useTranslation } from "@/lib/i18n";

/* eslint-disable @typescript-eslint/no-explicit-any */

export interface Column<T = any> {
  key: string;
  label: string;
  sortable?: boolean;
  render?: (value: any, row: T, index: number) => React.ReactNode;
  align?: "left" | "center" | "right";
  width?: string;
}

const ROWS_PER_PAGE_OPTIONS = [10, 25, 50, 100] as const;

interface Props<T = any> {
  data: T[];
  columns: Column<T>[];
  title?: string;
  searchKeys?: string[];
  exportFilename?: string;
  emptyMessage?: string;
  maxRows?: number;
  compact?: boolean;
  rowsPerPage?: number;
}

export default function DataTable<T extends Record<string, any>>({
  data,
  columns,
  title,
  searchKeys = [],
  exportFilename,
  emptyMessage = "No data available",
  maxRows = 200,
  compact = false,
  rowsPerPage: initialRowsPerPage = 25,
}: Props<T>) {
  const { t } = useTranslation();
  const [sortKey, setSortKey] = useState<string>("");
  const [sortAsc, setSortAsc] = useState(true);
  const [search, setSearch] = useState("");
  const [page, setPage] = useState(0);
  const [rowsPerPage, setRowsPerPage] = useState(initialRowsPerPage);

  const toggleSort = useCallback(
    (key: string) => {
      if (sortKey === key) {
        setSortAsc((prev) => !prev);
      } else {
        setSortKey(key);
        setSortAsc(true);
      }
    },
    [sortKey]
  );

  // Reset to first page when search, sort, or rowsPerPage changes
  const handleSearchChange = useCallback((value: string) => {
    setSearch(value);
    setPage(0);
  }, []);

  const handleRowsPerPageChange = useCallback((value: number) => {
    setRowsPerPage(value);
    setPage(0);
  }, []);

  const filtered = useMemo(() => {
    let result = [...data];

    // Search filter
    if (search && searchKeys.length > 0) {
      const q = search.toLowerCase();
      result = result.filter((row) =>
        searchKeys.some((k) => String(row[k] ?? "").toLowerCase().includes(q))
      );
    }

    // Sort
    if (sortKey) {
      result.sort((a, b) => {
        let va = a[sortKey];
        let vb = b[sortKey];
        if (typeof va === "string") va = va.toLowerCase();
        if (typeof vb === "string") vb = vb.toLowerCase();
        if (va == null) return 1;
        if (vb == null) return -1;
        if (va < vb) return sortAsc ? -1 : 1;
        if (va > vb) return sortAsc ? 1 : -1;
        return 0;
      });
    }

    return result.slice(0, maxRows);
  }, [data, search, searchKeys, sortKey, sortAsc, maxRows]);

  // Pagination
  const totalPages = Math.max(1, Math.ceil(filtered.length / rowsPerPage));
  const safePage = Math.min(page, totalPages - 1);
  const paginatedRows = useMemo(() => {
    const start = safePage * rowsPerPage;
    return filtered.slice(start, start + rowsPerPage);
  }, [filtered, safePage, rowsPerPage]);

  const cellPad = compact ? "px-3 py-1.5" : "px-4 py-2.5";
  const textSize = compact ? "text-[11px]" : "text-xs";

  return (
    <div className="rounded-2xl bg-white/80 dark:bg-white/[0.02] border border-slate-200 dark:border-white/[0.06] overflow-hidden">
      {/* Toolbar */}
      {(title || searchKeys.length > 0 || exportFilename) && (
        <div className="flex items-center justify-between px-4 py-3 border-b border-slate-200 dark:border-white/[0.06]">
          <div className="flex items-center gap-3">
            {title && (
              <h3 className="text-sm font-semibold text-[var(--text-primary)]">{title}</h3>
            )}
            <span className="text-[10px] text-[var(--text-secondary)]">
              {filtered.length} of {data.length}
            </span>
          </div>
          <div className="flex items-center gap-2">
            {searchKeys.length > 0 && (
              <div className="relative">
                <Search className="w-3.5 h-3.5 absolute left-2.5 top-1/2 -translate-y-1/2 text-[var(--text-secondary)]" />
                <input
                  value={search}
                  onChange={(e) => handleSearchChange(e.target.value)}
                  placeholder={t("table.search")}
                  aria-label={t("btn.search")}
                  className="bg-slate-100 dark:bg-white/[0.04] border border-slate-200 dark:border-white/[0.08] rounded-lg pl-8 pr-7 py-1.5 text-xs text-[var(--text-primary)] placeholder-slate-400 dark:placeholder-white/20 focus:outline-hidden focus:border-ocean-500/30 w-44"
                />
                {search && (
                  <button
                    onClick={() => handleSearchChange("")}
                    aria-label="Clear search"
                    className="absolute right-2 top-1/2 -translate-y-1/2 text-white/20 hover:text-white/50"
                  >
                    <X className="w-3 h-3" />
                  </button>
                )}
              </div>
            )}
            {exportFilename && (
              <>
                <button
                  onClick={() => exportToCSV(filtered, exportFilename)}
                  aria-label="Export as CSV"
                  className="flex items-center gap-1 px-2 py-1.5 text-[10px] text-[var(--text-secondary)] hover:text-ocean-400 bg-slate-100 dark:bg-white/[0.03] border border-slate-200 dark:border-white/[0.06] rounded-lg transition-colors"
                >
                  <Download className="w-3 h-3" /> CSV
                </button>
                <button
                  onClick={() => exportToExcel(filtered, exportFilename)}
                  aria-label="Export as Excel"
                  className="flex items-center gap-1 px-2 py-1.5 text-[10px] text-[var(--success)] opacity-70 hover:opacity-100 bg-slate-100 dark:bg-white/[0.03] border border-slate-200 dark:border-white/[0.06] rounded-lg transition-colors"
                >
                  <Download className="w-3 h-3" /> Excel
                </button>
              </>
            )}
          </div>
        </div>
      )}

      {/* Table */}
      <div className="overflow-x-auto">
        <table className="w-full min-w-[600px]">
          <thead>
            <tr className="border-b border-slate-200 dark:border-white/[0.06]">
              {columns.map((col) => (
                <th
                  key={col.key}
                  scope="col"
                  aria-sort={col.sortable !== false && sortKey === col.key ? (sortAsc ? "ascending" : "descending") : undefined}
                  className={`${cellPad} ${textSize} font-medium text-[var(--text-secondary)] ${
                    col.align === "right" ? "text-right" : col.align === "center" ? "text-center" : "text-left"
                  } ${col.sortable !== false ? "cursor-pointer select-none hover:text-ocean-400 transition-colors" : ""}`}
                  style={col.width ? { width: col.width } : undefined}
                  onClick={() => col.sortable !== false && toggleSort(col.key)}
                >
                  <div className={`flex items-center gap-1 ${col.align === "right" ? "justify-end" : ""}`}>
                    {col.label}
                    {col.sortable !== false && sortKey === col.key && (
                      sortAsc ? <ChevronUp className="w-3 h-3" /> : <ChevronDown className="w-3 h-3" />
                    )}
                  </div>
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {paginatedRows.length === 0 ? (
              <tr>
                <td colSpan={columns.length} className="px-4 py-8 text-center text-xs text-[var(--text-secondary)]">
                  {emptyMessage}
                </td>
              </tr>
            ) : (
              paginatedRows.map((row, idx) => (
                <tr
                  key={idx}
                  className="border-b border-slate-100 dark:border-white/[0.03] hover:bg-slate-50 dark:hover:bg-white/[0.02] transition-colors"
                >
                  {columns.map((col) => (
                    <td
                      key={col.key}
                      className={`${cellPad} ${textSize} text-[var(--text-primary)] ${
                        col.align === "right" ? "text-right" : col.align === "center" ? "text-center" : ""
                      }`}
                    >
                      {col.render
                        ? col.render(row[col.key], row, safePage * rowsPerPage + idx)
                        : row[col.key] ?? "—"}
                    </td>
                  ))}
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>

      {/* Pagination Controls */}
      {filtered.length > 0 && (
        <div className="flex items-center justify-between px-4 py-2.5 border-t border-slate-200 dark:border-white/[0.06]">
          <div className="flex items-center gap-2">
            <span className="text-[10px] text-[var(--text-secondary)]">{t("table.rows_per_page")}</span>
            <select
              value={rowsPerPage}
              onChange={(e) => handleRowsPerPageChange(Number(e.target.value))}
              aria-label="Rows per page"
              className="bg-slate-100 dark:bg-white/[0.04] border border-slate-200 dark:border-white/[0.08] rounded-md px-1.5 py-0.5 text-[10px] text-[var(--text-primary)] focus:outline-hidden focus:border-ocean-500/30 cursor-pointer"
            >
              {ROWS_PER_PAGE_OPTIONS.map((opt) => (
                <option key={opt} value={opt} className="bg-slate-900">{opt}</option>
              ))}
            </select>
          </div>

          <div className="flex items-center gap-3">
            <span className="text-[10px] text-[var(--text-secondary)] tabular-nums">
              {safePage * rowsPerPage + 1}&ndash;{Math.min((safePage + 1) * rowsPerPage, filtered.length)} {t("table.of")} {filtered.length}
            </span>
            <div className="flex items-center gap-1">
              <button
                onClick={() => setPage((p) => Math.max(0, p - 1))}
                disabled={safePage === 0}
                aria-label={t("btn.previous")}
                className="p-1 rounded-md border border-slate-200 dark:border-white/[0.06] text-[var(--text-secondary)] hover:text-ocean-400 hover:border-ocean-500/30 disabled:opacity-30 disabled:cursor-not-allowed transition-colors"
              >
                <ChevronLeft className="w-3.5 h-3.5" />
              </button>
              <span className="text-[10px] text-[var(--text-secondary)] tabular-nums min-w-[64px] text-center">
                {t("table.page")} {safePage + 1} {t("table.of")} {totalPages}
              </span>
              <button
                onClick={() => setPage((p) => Math.min(totalPages - 1, p + 1))}
                disabled={safePage >= totalPages - 1}
                aria-label={t("btn.next")}
                className="p-1 rounded-md border border-slate-200 dark:border-white/[0.06] text-[var(--text-secondary)] hover:text-ocean-400 hover:border-ocean-500/30 disabled:opacity-30 disabled:cursor-not-allowed transition-colors"
              >
                <ChevronRight className="w-3.5 h-3.5" />
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

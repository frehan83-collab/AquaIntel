/**
 * Export Utilities
 * CSV and Excel (.xlsx) export for data tables.
 * Note: xlsx (SheetJS) is dynamically imported to avoid adding ~500KB to the initial bundle.
 */

/**
 * Export data as Excel (.xlsx) workbook.
 * Formats dates and numbers; includes column headers.
 * SheetJS is loaded on demand — only when the user clicks export.
 */
export async function exportToExcel(data: Record<string, any>[], filename: string): Promise<void> {
  if (!data || data.length === 0) return;

  // Dynamic import — xlsx is ~500KB, only load when actually needed
  const XLSX = await import("xlsx");

  // Normalize values for spreadsheet (flatten objects, format dates)
  const cleaned = data.map((row) => {
    const out: Record<string, any> = {};
    for (const [k, v] of Object.entries(row)) {
      if (v == null) {
        out[k] = "";
      } else if (v instanceof Date) {
        out[k] = v;
      } else if (typeof v === "object") {
        out[k] = JSON.stringify(v);
      } else {
        out[k] = v;
      }
    }
    return out;
  });

  const ws = XLSX.utils.json_to_sheet(cleaned);

  // Auto-size columns based on header + first 20 rows of content
  const keys = Object.keys(cleaned[0] || {});
  ws["!cols"] = keys.map((key) => {
    let maxLen = key.length;
    for (let i = 0; i < Math.min(cleaned.length, 20); i++) {
      const val = String(cleaned[i][key] ?? "");
      if (val.length > maxLen) maxLen = val.length;
    }
    return { wch: Math.min(maxLen + 2, 40) };
  });

  const wb = XLSX.utils.book_new();
  XLSX.utils.book_append_sheet(wb, ws, "Data");
  XLSX.writeFile(wb, `${filename}_${new Date().toISOString().slice(0, 10)}.xlsx`);
}

export function exportToCSV(data: Record<string, any>[], filename: string): void {
  if (!data || data.length === 0) return;

  // Get all unique keys across all rows
  const keys = Array.from(new Set(data.flatMap(row => Object.keys(row))));

  // Build CSV content
  const header = keys.map(k => `"${k}"`).join(",");
  const rows = data.map(row =>
    keys.map(k => {
      const val = row[k];
      if (val == null) return "";
      if (typeof val === "object") return `"${JSON.stringify(val).replace(/"/g, '""')}"`;
      return `"${String(val).replace(/"/g, '""')}"`;
    }).join(",")
  );

  const csv = [header, ...rows].join("\n");
  const blob = new Blob(["\uFEFF" + csv], { type: "text/csv;charset=utf-8;" });
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = `${filename}_${new Date().toISOString().slice(0, 10)}.csv`;
  link.click();
  URL.revokeObjectURL(url);
}

// Helper Excel (SheetJS). Ekspor .xlsx & baca file .xlsx/.xls/.csv jadi baris JSON.
import * as XLSX from "xlsx";

/** Unduh data sebagai file .xlsx dengan satu sheet. */
export function exportXLSX(title: string, headers: string[], rows: (string | number)[][]) {
  const ws = XLSX.utils.aoa_to_sheet([headers, ...rows]);
  // lebar kolom menyesuaikan isi (min 10, max 40 karakter)
  ws["!cols"] = headers.map((h, i) => {
    const maxLen = Math.max(
      String(h).length,
      ...rows.map((r) => String(r[i] ?? "").length),
    );
    return { wch: Math.min(Math.max(maxLen + 2, 10), 40) };
  });
  const wb = XLSX.utils.book_new();
  XLSX.utils.book_append_sheet(wb, ws, title.slice(0, 31) || "Sheet1");
  const fname = `${title.replace(/[^\w\- ]+/g, "").replace(/\s+/g, "-")}-${new Date()
    .toISOString().slice(0, 10)}.xlsx`;
  XLSX.writeFile(wb, fname);
}

/** Baca sheet pertama dari file Excel/CSV → array objek, key = header huruf kecil. */
export async function readSheet(file: File): Promise<Record<string, string>[]> {
  const buf = await file.arrayBuffer();
  const wb = XLSX.read(buf, { type: "array" });
  const ws = wb.Sheets[wb.SheetNames[0]];
  if (!ws) return [];
  const raw = XLSX.utils.sheet_to_json<Record<string, unknown>>(ws, {
    raw: false, defval: "",
  });
  return raw.map((row) => {
    const out: Record<string, string> = {};
    for (const [k, v] of Object.entries(row)) {
      out[String(k).trim().toLowerCase()] = String(v ?? "").trim();
    }
    return out;
  });
}

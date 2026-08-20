"use client";
import { useEffect } from "react";
import { Plus, X } from "lucide-react";
import { rupiah } from "@/lib/format";
import { Input } from "@/components/ui/input";
import { Select } from "@/components/ui/form";

export type Termin = {
  kind: "tunai" | "dp" | "tempo" | "po_berikutnya" | "custom";
  due_date: string;   // "" berarti tanpa tanggal
  amount: string;
};

const JENIS: { v: Termin["kind"]; label: string; hint: string }[] = [
  { v: "tunai", label: "Tunai", hint: "dibayar sekarang" },
  { v: "dp", label: "DP / uang muka", hint: "dibayar di muka" },
  { v: "tempo", label: "Tempo", hint: "jatuh tempo tanggal tertentu" },
  { v: "po_berikutnya", label: "Bayar di PO berikutnya", hint: "tanpa tanggal" },
  { v: "custom", label: "Custom", hint: "kesepakatan khusus" },
];

/** Jenis yang memang tidak punya tanggal jatuh tempo. */
const TANPA_TANGGAL = new Set<Termin["kind"]>(["po_berikutnya"]);

export function terminDefault(total: number, tanggal: string): Termin[] {
  return [{ kind: "tunai", due_date: tanggal, amount: String(total || 0) }];
}

/**
 * Editor jadwal pembayaran faktur.
 *
 * Menegakkan invarian yang sama dengan backend: total termin harus PERSIS
 * sama dengan total faktur. Ditampilkan sebagai "selisih" yang harus nol —
 * kalau tidak, tombol simpan di form pemanggil dimatikan lewat `onValid`.
 * Backend tetap menolak juga; ini hanya supaya orang tahu sebelum menekan
 * simpan, bukan pengganti validasi di sana.
 */
export function TerminEditor({
  total, tanggal, value, onChange, onValid,
}: {
  total: number;
  tanggal: string;
  value: Termin[];
  onChange: (t: Termin[]) => void;
  onValid?: (ok: boolean) => void;
}) {
  const jumlah = value.reduce((s, t) => s + Number(t.amount || 0), 0);
  const selisih = Math.round((total - jumlah) * 100) / 100;
  const valid = value.length > 0 && selisih === 0;

  useEffect(() => { onValid?.(valid); }, [valid, onValid]);

  function ubah(i: number, patch: Partial<Termin>) {
    const next = value.map((t, j) => (j === i ? { ...t, ...patch } : t));
    // Jenis tanpa tanggal tidak boleh menyimpan tanggal sisa dari pilihan
    // sebelumnya — backend memaknai tanggal kosong sebagai "belum ada tempo".
    if (patch.kind && TANPA_TANGGAL.has(patch.kind)) next[i].due_date = "";
    onChange(next);
  }

  function tambah() {
    onChange([...value, {
      kind: "tempo",
      due_date: tanggal,
      amount: selisih > 0 ? String(selisih) : "0",
    }]);
  }

  function hapus(i: number) {
    onChange(value.filter((_, j) => j !== i));
  }

  return (
    <div className="space-y-2">
      {value.map((t, i) => (
        <div key={i} className="flex items-start gap-2">
          <Select value={t.kind} onChange={(e) => ubah(i, { kind: e.target.value as Termin["kind"] })}
            className="flex-[2]">
            {JENIS.map((j) => <option key={j.v} value={j.v}>{j.label}</option>)}
          </Select>
          <Input type="date" value={t.due_date} className="flex-[2]"
            disabled={TANPA_TANGGAL.has(t.kind)}
            onChange={(e) => ubah(i, { due_date: e.target.value })} />
          <Input type="number" min={0} value={t.amount} className="flex-[2]"
            placeholder="Rp" onChange={(e) => ubah(i, { amount: e.target.value })} />
          <button type="button" onClick={() => hapus(i)}
            disabled={value.length === 1}
            aria-label="Hapus termin"
            className="mt-2 text-ink-subtle hover:text-danger disabled:opacity-30">
            <X size={16} />
          </button>
        </div>
      ))}

      <div className="flex items-center justify-between pt-1">
        <button type="button" onClick={tambah}
          className="flex items-center gap-1 text-caption text-primary">
          <Plus size={14} /> Tambah termin
        </button>
        <p className={`text-caption tabular-nums ${selisih === 0 ? "text-ink-subtle" : "text-danger"}`}>
          {selisih === 0
            ? `Pas dengan total faktur (${rupiah(total)})`
            : selisih > 0
              ? `Kurang ${rupiah(selisih)} dari total faktur`
              : `Lebih ${rupiah(-selisih)} dari total faktur`}
        </p>
      </div>
    </div>
  );
}

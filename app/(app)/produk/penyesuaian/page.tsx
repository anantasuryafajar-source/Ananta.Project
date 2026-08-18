"use client";
import { useEffect, useState } from "react";
import { Plus, Trash2, Calculator, Save, TriangleAlert } from "lucide-react";
import { api } from "@/lib/api";
import { rupiah, tanggal } from "@/lib/format";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Field, Select, Textarea, NumCell } from "@/components/ui/form";
import { Input } from "@/components/ui/input";

/**
 * Penyesuaian stok — memasukkan hasil hitung fisik gudang.
 *
 * Alurnya SENGAJA dua langkah: "Hitung Selisih" lalu "Simpan". Penyesuaian
 * menulis ulang saldo stok sekaligus memposting jurnal, jadi user harus
 * melihat dulu apa yang akan berubah. Tombol simpan baru hidup setelah
 * pratinjau, dan pratinjau dibatalkan setiap kali input diubah supaya yang
 * disetujui tidak pernah berbeda dari yang disimpan.
 *
 * Jumlah diketik dalam DUA kolom, dus dan botol, karena begitulah client
 * menghitung ("15 dus 11 botol"). Lihat backend models/stock_adjustment.py.
 */

type Product = {
  id: string; name: string; pack_size: number;
  pack_purchase_price: string;
};
type Warehouse = { id: string; name: string };

type Baris = {
  product_id: string;
  qty_dus: string;
  qty_botol: string;
  modal_per_dus: string;
  note: string;
};

type PreviewLine = {
  product_id: string; product_name: string; pack_size: number;
  qty_before: string; qty_counted: string; qty_diff: string;
  unit_cost: string; line_value: string; note: string | null;
  tercantum: boolean;
  before_display: string; counted_display: string; diff_display: string;
};
type Preview = {
  lines: PreviewLine[];
  total_value: string;
  jumlah_berubah: number;
  warnings: string[];
};
type Adjustment = {
  id: string; number: string; date: string; mode: string;
  status: string; total_value: string; notes: string | null;
};

const barisKosong: Baris = {
  product_id: "", qty_dus: "", qty_botol: "", modal_per_dus: "", note: "",
};

export default function PenyesuaianStokPage() {
  const [produk, setProduk] = useState<Product[]>([]);
  const [gudang, setGudang] = useState<Warehouse[]>([]);
  const [riwayat, setRiwayat] = useState<Adjustment[] | null>(null);

  const [tgl, setTgl] = useState(() => new Date().toISOString().slice(0, 10));
  const [mode, setMode] = useState<"opening" | "opname">("opname");
  const [warehouseId, setWarehouseId] = useState("");
  const [lengkap, setLengkap] = useState(false);
  const [catatan, setCatatan] = useState("");
  const [baris, setBaris] = useState<Baris[]>([{ ...barisKosong }]);

  const [preview, setPreview] = useState<Preview | null>(null);
  const [sibuk, setSibuk] = useState(false);
  const [error, setError] = useState("");
  const [sukses, setSukses] = useState("");

  function muatRiwayat() {
    api<Adjustment[]>("/stock-adjustments").then(setRiwayat).catch(() => {});
  }

  useEffect(() => {
    api<Product[]>("/products?limit=200").then(setProduk).catch((e) => setError(e.message));
    api<Warehouse[]>("/warehouses")
      .then((g) => { setGudang(g); if (g[0]) setWarehouseId(g[0].id); })
      .catch(() => {});
    muatRiwayat();
  }, []);

  /** Setiap perubahan input membatalkan pratinjau — lihat catatan di atas. */
  function ubah(i: number, patch: Partial<Baris>) {
    setBaris((b) => b.map((r, n) => (n === i ? { ...r, ...patch } : r)));
    setPreview(null);
    setSukses("");
  }
  function tambahBaris() {
    setBaris((b) => [...b, { ...barisKosong }]);
    setPreview(null);
  }
  function hapusBaris(i: number) {
    setBaris((b) => (b.length === 1 ? b : b.filter((_, n) => n !== i)));
    setPreview(null);
  }

  function payloadBaris() {
    return baris
      .filter((r) => r.product_id)
      .map((r) => ({
        product_id: r.product_id,
        qty_dus: r.qty_dus || "0",
        qty_botol: r.qty_botol || "0",
        modal_per_dus: r.modal_per_dus === "" ? null : r.modal_per_dus,
        note: r.note || null,
      }));
  }

  async function hitung() {
    setError(""); setSukses(""); setSibuk(true);
    try {
      setPreview(await api<Preview>("/stock-adjustments/preview", {
        method: "POST",
        body: JSON.stringify({
          warehouse_id: warehouseId || null,
          hitungan_lengkap: lengkap,
          lines: payloadBaris(),
        }),
      }));
    } catch (e) {
      setPreview(null);
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setSibuk(false);
    }
  }

  async function simpan() {
    setError(""); setSibuk(true);
    try {
      const adj = await api<Adjustment>("/stock-adjustments", {
        method: "POST",
        body: JSON.stringify({
          date: tgl, mode, notes: catatan || null,
          warehouse_id: warehouseId || null,
          hitungan_lengkap: lengkap,
          lines: payloadBaris(),
        }),
      });
      setSukses(`Tersimpan sebagai ${adj.number}. Stok sudah diperbarui.`);
      setBaris([{ ...barisKosong }]);
      setCatatan("");
      setLengkap(false);
      setPreview(null);
      muatRiwayat();
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setSibuk(false);
    }
  }

  const adaBaris = payloadBaris().length > 0;

  return (
    <div className="space-y-6 p-6">
      {/* ---------------------------------------------------- form hitungan */}
      <Card>
        <div className="grid gap-4 md:grid-cols-4">
          <Field label="Tanggal hitung">
            <Input type="date" value={tgl} onChange={(e) => setTgl(e.target.value)} />
          </Field>
          <Field
            label="Jenis"
            hint={mode === "opening"
              ? "Masuk ke ekuitas — tidak memengaruhi laba rugi."
              : "Selisihnya jadi beban/pendapatan periode berjalan."}
          >
            <Select
              value={mode}
              onChange={(e) => { setMode(e.target.value as "opening" | "opname"); setPreview(null); }}
            >
              <option value="opname">Selisih opname (hitung rutin)</option>
              <option value="opening">Stok awal (pertama kali)</option>
            </Select>
          </Field>
          <Field label="Gudang">
            <Select
              value={warehouseId}
              onChange={(e) => { setWarehouseId(e.target.value); setPreview(null); }}
            >
              {gudang.map((g) => <option key={g.id} value={g.id}>{g.name}</option>)}
            </Select>
          </Field>
          <Field label="Catatan dokumen">
            <Input
              value={catatan}
              onChange={(e) => setCatatan(e.target.value)}
              placeholder="mis. Hitung fisik 13 Agustus"
            />
          </Field>
        </div>

        <div className="mt-4 overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-line text-left text-caption text-ink-muted">
                <th className="py-2 pr-2 font-medium">Produk</th>
                <th className="w-24 px-2 py-2 text-right font-medium">Dus</th>
                <th className="w-24 px-2 py-2 text-right font-medium">Botol</th>
                <th className="w-36 px-2 py-2 text-right font-medium">Modal / dus</th>
                <th className="px-2 py-2 font-medium">Keterangan</th>
                <th className="w-10" />
              </tr>
            </thead>
            <tbody>
              {baris.map((r, i) => {
                const p = produk.find((x) => x.id === r.product_id);
                return (
                  <tr key={i} className="border-b border-line/60 align-top">
                    <td className="py-2 pr-2">
                      <Select
                        value={r.product_id}
                        onChange={(e) => ubah(i, { product_id: e.target.value })}
                      >
                        <option value="">— pilih produk —</option>
                        {produk.map((x) => (
                          <option key={x.id} value={x.id}>{x.name}</option>
                        ))}
                      </Select>
                      {p && (
                        <p className="mt-1 text-caption text-ink-subtle">
                          1 dus = {p.pack_size} botol
                        </p>
                      )}
                    </td>
                    <td className="px-2 py-2">
                      <NumCell
                        value={r.qty_dus} placeholder="0"
                        onChange={(e) => ubah(i, { qty_dus: e.target.value })}
                      />
                    </td>
                    <td className="px-2 py-2">
                      <NumCell
                        value={r.qty_botol} placeholder="0"
                        onChange={(e) => ubah(i, { qty_botol: e.target.value })}
                      />
                    </td>
                    <td className="px-2 py-2">
                      <NumCell
                        value={r.modal_per_dus}
                        placeholder={p ? Number(p.pack_purchase_price).toLocaleString("id-ID") : "otomatis"}
                        onChange={(e) => ubah(i, { modal_per_dus: e.target.value })}
                      />
                    </td>
                    <td className="px-2 py-2">
                      <Input
                        value={r.note}
                        onChange={(e) => ubah(i, { note: e.target.value })}
                        placeholder="cukai biru, returan, kondisi…"
                      />
                    </td>
                    <td className="py-2">
                      <button
                        type="button" onClick={() => hapusBaris(i)}
                        className="rounded-[var(--radius-button)] p-1.5 text-ink-muted hover:bg-surface-sunken"
                        aria-label="Hapus baris"
                      >
                        <Trash2 size={16} />
                      </button>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>

        <div className="mt-3 flex flex-wrap items-center justify-between gap-3">
          <Button variant="secondary" onClick={tambahBaris}>
            <Plus size={16} /> Tambah baris
          </Button>
          <label className="flex items-center gap-2 text-sm text-ink-muted">
            <input
              type="checkbox" checked={lengkap}
              onChange={(e) => { setLengkap(e.target.checked); setPreview(null); }}
              className="h-4 w-4 rounded border-line accent-[var(--primary)]"
            />
            Hitungan lengkap — produk yang tidak tercantum dianggap habis
          </label>
        </div>

        <p className="mt-2 text-caption text-ink-subtle">
          Isi jumlah <strong>fisik yang ada di gudang</strong>, bukan selisihnya —
          sistem menghitung sendiri selisihnya terhadap catatan. Kolom modal
          hanya dipakai bila stok bertambah; kosongkan untuk memakai modal yang
          sudah tercatat.
        </p>

        <div className="mt-4 flex flex-wrap gap-2">
          <Button onClick={hitung} disabled={sibuk || !adaBaris}>
            <Calculator size={16} /> Hitung selisih
          </Button>
          <Button
            onClick={simpan}
            disabled={sibuk || !preview || preview.jumlah_berubah === 0}
          >
            <Save size={16} /> Simpan penyesuaian
          </Button>
        </div>

        {error && <p className="mt-3 text-sm text-danger">{error}</p>}
        {sukses && <p className="mt-3 text-sm text-primary">{sukses}</p>}
      </Card>

      {/* ------------------------------------------------------- pratinjau */}
      {preview && (
        <Card>
          <h2 className="font-display text-lg font-semibold text-ink">
            Yang akan berubah
          </h2>
          <p className="mt-1 text-sm text-ink-muted">
            {preview.jumlah_berubah === 0
              ? "Tidak ada selisih — hitungan fisik sama dengan catatan sistem."
              : `${preview.jumlah_berubah} produk berubah. Belum ada yang disimpan.`}
          </p>

          {preview.warnings.length > 0 && (
            <div className="mt-3 rounded-[var(--radius-card)] border border-line bg-surface-sunken p-3">
              {preview.warnings.map((w, i) => (
                <p key={i} className="flex gap-2 text-sm text-ink-muted">
                  <TriangleAlert size={16} className="mt-0.5 shrink-0" />
                  <span>{w}</span>
                </p>
              ))}
            </div>
          )}

          <div className="mt-4 overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-line text-left text-caption text-ink-muted">
                  <th className="py-2 pr-2 font-medium">Produk</th>
                  <th className="px-2 py-2 font-medium">Catatan sistem</th>
                  <th className="px-2 py-2 font-medium">Hitung fisik</th>
                  <th className="px-2 py-2 font-medium">Selisih</th>
                  <th className="px-2 py-2 text-right font-medium">Nilai</th>
                </tr>
              </thead>
              <tbody>
                {preview.lines.map((l) => (
                  <tr key={l.product_id} className="border-b border-line/60">
                    <td className="py-2 pr-2">
                      {l.product_name}
                      {!l.tercantum && (
                        <span className="ml-2 rounded-[var(--radius-badge)] bg-surface-sunken px-1.5 py-0.5 text-caption text-ink-subtle">
                          tidak dihitung
                        </span>
                      )}
                      {l.note && (
                        <p className="text-caption text-ink-subtle">{l.note}</p>
                      )}
                    </td>
                    <td className="px-2 py-2 text-ink-muted">{l.before_display}</td>
                    <td className="px-2 py-2">{l.counted_display}</td>
                    <td className={`px-2 py-2 font-medium ${
                      Number(l.qty_diff) === 0 ? "text-ink-subtle"
                        : Number(l.qty_diff) > 0 ? "text-primary" : "text-danger"
                    }`}>
                      {Number(l.qty_diff) === 0 ? "—" : l.diff_display}
                    </td>
                    <td className="px-2 py-2 text-right tabular-nums">
                      {rupiah(l.line_value)}
                    </td>
                  </tr>
                ))}
              </tbody>
              <tfoot>
                <tr>
                  <td colSpan={4} className="py-2 pr-2 text-right font-medium text-ink">
                    Nilai bersih penyesuaian
                  </td>
                  <td className="px-2 py-2 text-right font-semibold tabular-nums text-ink">
                    {rupiah(preview.total_value)}
                  </td>
                </tr>
              </tfoot>
            </table>
          </div>
        </Card>
      )}

      {/* -------------------------------------------------------- riwayat */}
      <Card className="overflow-hidden p-0">
        <h2 className="px-4 pt-4 font-display text-lg font-semibold text-ink">
          Riwayat penyesuaian
        </h2>
        {riwayat && riwayat.length === 0 && (
          <p className="px-4 pb-4 pt-2 text-sm text-ink-muted">
            Belum ada penyesuaian stok.
          </p>
        )}
        {riwayat && riwayat.length > 0 && (
          <table className="mt-3 w-full text-sm">
            <thead>
              <tr className="border-y border-line text-left text-caption text-ink-muted">
                <th className="px-4 py-3 font-medium">Nomor</th>
                <th className="px-4 py-3 font-medium">Tanggal</th>
                <th className="px-4 py-3 font-medium">Jenis</th>
                <th className="px-4 py-3 font-medium">Catatan</th>
                <th className="px-4 py-3 text-right font-medium">Nilai</th>
              </tr>
            </thead>
            <tbody>
              {riwayat.map((a) => (
                <tr key={a.id} className="border-b border-line/60">
                  <td className="px-4 py-3 font-medium text-ink">{a.number}</td>
                  <td className="px-4 py-3 text-ink-muted">{tanggal(a.date)}</td>
                  <td className="px-4 py-3 text-ink-muted">
                    {a.mode === "opening" ? "Stok awal" : "Selisih opname"}
                  </td>
                  <td className="px-4 py-3 text-ink-muted">{a.notes ?? "—"}</td>
                  <td className="px-4 py-3 text-right tabular-nums">
                    {rupiah(a.total_value)}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </Card>
    </div>
  );
}

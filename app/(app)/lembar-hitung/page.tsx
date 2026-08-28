"use client";
import { useEffect, useState } from "react";
import { Plus, Trash2, Lock } from "lucide-react";
import { api } from "@/lib/api";
import { rupiah, tanggal } from "@/lib/format";
import { Topbar } from "@/components/ananta/topbar";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Modal } from "@/components/ui/modal";
import { Field, Select, NumCell } from "@/components/ui/form";

type BarisOut = {
  id: string; sequence: number; payee_name: string; jenis: string;
  dasar: string; persen: string | null; nominal: string | null;
  amount: string; paid_date: string | null;
  settlement_journal_id: string | null; note: string | null;
};
type Lembar = {
  id: string; number: string; date: string; invoice_id: string; status: string;
  penjualan: string; hpp_riil: string; hpp_dasar_komisi: string;
  modal_perjanjian: string | null; pengurang_per_dus: string | null;
  jumlah_dus: string; profit_bersama: string; bagian_asf: string;
  hidden_margin: string; note: string | null; lines: BarisOut[];
};
type Invoice = { id: string; number: string; status: string; total: string };
type Opsi = { kode: string; keterangan: string };
type DaftarDasar = { dasar: Opsi[]; jenis: Opsi[] };
type Pratinjau = {
  invoice_number: string; penjualan: string; hpp_riil: string;
  hpp_dasar_komisi: string; margin_riil: string; jumlah_dus: string;
  profit_bersama: string; bagian_asf: string; hidden_margin: string;
  total_hak: string; melebihi_margin: boolean;
  baris: { payee_name: string; jenis: string; dasar: string;
           keterangan_dasar: string; amount: string }[];
};

/** Baris kesepakatan seperti yang diketik user (semua string, seperti form). */
type BarisForm = {
  payee_name: string; jenis: string; dasar: string;
  persen: string; nominal: string;
};

const today = () => new Date().toISOString().slice(0, 10);

/** Hanya faktur yang barangnya sudah keluar yang punya HPP di jurnal. */
const FAKTUR_SAH = new Set(["posted", "paid", "overdue"]);

const LABEL_STATUS: Record<string, string> = {
  draft: "Draft", disetujui: "Disetujui", ditransfer: "Ditransfer",
  batal: "Batal",
};
const LABEL_JENIS: Record<string, string> = {
  komisi: "Komisi pihak ketiga", bagi_hasil: "Hak mitra",
};

const BARIS_KOSONG: BarisForm = {
  payee_name: "", jenis: "komisi", dasar: "margin_riil",
  persen: "", nominal: "",
};

export default function LembarHitungPage() {
  const [items, setItems] = useState<Lembar[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [sibuk, setSibuk] = useState<string | null>(null);

  const [opsi, setOpsi] = useState<DaftarDasar | null>(null);
  const [invoices, setInvoices] = useState<Invoice[]>([]);

  const [open, setOpen] = useState(false);
  const [invoiceId, setInvoiceId] = useState("");
  const [modal, setModal] = useState("");
  const [hppDasar, setHppDasar] = useState("");
  const [pengurang, setPengurang] = useState("");
  const [baris, setBaris] = useState<BarisForm[]>([{ ...BARIS_KOSONG }]);
  const [pratinjau, setPratinjau] = useState<Pratinjau | null>(null);
  const [formError, setFormError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);

  function muat() {
    api<Lembar[]>("/profit-sheets").then(setItems).catch((e) => setError(e.message));
  }
  useEffect(() => {
    muat();
    api<DaftarDasar>("/profit-sheets/dasar").then(setOpsi).catch(() => {});
  }, []);

  function buka() {
    setFormError(null); setPratinjau(null);
    setInvoiceId(""); setModal(""); setHppDasar(""); setPengurang("");
    setBaris([{ ...BARIS_KOSONG }]);
    setOpen(true);
    api<Invoice[]>("/invoices")
      .then((all) => setInvoices(all.filter((i) => FAKTUR_SAH.has(i.status))))
      .catch(() => setInvoices([]));
  }

  function ubahBaris(i: number, patch: Partial<BarisForm>) {
    setBaris((b) => b.map((x, n) => (n === i ? { ...x, ...patch } : x)));
    setPratinjau(null);
  }

  /** Kirim ke backend untuk dihitung. Sengaja TIDAK dihitung di sini:
   *  rumusnya cuma boleh hidup di satu tempat, kalau tidak dua sisi akan
   *  menampilkan angka berbeda untuk kesepakatan yang sama. */
  async function hitung() {
    setFormError(null);
    if (!invoiceId) return setFormError("Pilih fakturnya dulu.");
    try {
      const r = await api<Pratinjau>("/profit-sheets/pratinjau", {
        method: "POST",
        body: JSON.stringify({
          invoice_id: invoiceId, baris: bodyBaris(),
          modal_perjanjian: modal || null,
          hpp_dasar_komisi: hppDasar || null,
          pengurang_per_dus: pengurang || null,
        }),
      });
      setPratinjau(r);
    } catch (e) {
      setPratinjau(null);
      setFormError(e instanceof Error ? e.message : "Gagal menghitung.");
    }
  }

  function bodyBaris() {
    return baris.map((b) => ({
      payee_name: b.payee_name.trim(),
      jenis: b.jenis,
      dasar: b.dasar,
      persen: b.dasar === "nominal" ? null : b.persen || null,
      nominal: b.dasar === "nominal" ? b.nominal || null : null,
    }));
  }

  async function simpan() {
    setFormError(null);
    if (!invoiceId) return setFormError("Pilih fakturnya dulu.");
    if (baris.some((b) => !b.payee_name.trim())) {
      return setFormError("Setiap baris harus punya nama penerima.");
    }
    setSaving(true);
    try {
      await api("/profit-sheets", {
        method: "POST",
        body: JSON.stringify({
          invoice_id: invoiceId, date: today(), baris: bodyBaris(),
          modal_perjanjian: modal || null,
          hpp_dasar_komisi: hppDasar || null,
          pengurang_per_dus: pengurang || null,
        }),
      });
      setOpen(false);
      muat();
    } catch (e) {
      setFormError(e instanceof Error ? e.message : "Gagal menyimpan.");
    } finally { setSaving(false); }
  }

  async function aksi(id: string, jalur: string, body: object) {
    setSibuk(id); setError(null);
    try {
      await api(`/profit-sheets/${id}/${jalur}`, {
        method: "POST", body: JSON.stringify(body),
      });
      muat();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Gagal.");
    } finally { setSibuk(null); }
  }

  return (
    <>
      <Topbar title="Lembar Hitung" />
      <div className="p-6">
        <Card className="mb-4">
          <p className="text-sm text-ink">
            Kalkulator kesepakatan per faktur: bagi hasil mitra dan komisi pihak
            ketiga.
          </p>
          <p className="mt-1 text-caption text-ink-subtle">
            Angkanya tidak pernah muncul di faktur customer. Beban &amp; utang
            diakui saat lembar <b>disetujui</b>; transfer uangnya baru dibuka
            setelah faktur lunas.
          </p>
        </Card>

        {error && <Card className="mb-4"><p className="text-sm text-danger">{error}</p></Card>}

        <div className="mb-3 flex items-center justify-between">
          <h2 className="text-ink">Daftar lembar</h2>
          <Button onClick={buka}><Plus size={16} /> Lembar baru</Button>
        </div>

        {items === null ? (
          <Card><p className="text-sm text-ink-muted">Memuat…</p></Card>
        ) : items.length === 0 ? (
          <Card>
            <p className="text-sm text-ink-muted">
              Belum ada lembar hitung. Buat satu dari faktur yang sudah diposting.
            </p>
          </Card>
        ) : (
          <div className="space-y-4">
            {items.map((s) => (
              <Card key={s.id} className="p-0 overflow-hidden">
                <div className="flex flex-wrap items-baseline justify-between gap-2 border-b border-line px-4 py-3">
                  <div>
                    <span className="text-ink">{s.number}</span>
                    <span className="ml-2 text-caption text-ink-subtle">
                      {tanggal(s.date)}
                    </span>
                  </div>
                  <div className="flex items-center gap-3">
                    <span className="text-caption text-ink-muted">
                      {LABEL_STATUS[s.status] ?? s.status}
                    </span>
                    {s.status === "draft" && (
                      <Button variant="secondary" disabled={sibuk === s.id}
                        onClick={() => aksi(s.id, "approve", { date: today() })}>
                        Setujui
                      </Button>
                    )}
                    {s.status !== "batal" && (
                      <Button variant="ghost" disabled={sibuk === s.id}
                        onClick={() => aksi(s.id, "void",
                          { date: today(), reason: "dibatalkan dari UI" })}>
                        Batalkan
                      </Button>
                    )}
                  </div>
                </div>

                <div className="grid gap-3 px-4 py-3 text-sm sm:grid-cols-4">
                  <Angka label="Penjualan" nilai={s.penjualan} />
                  <Angka label="HPP riil" nilai={s.hpp_riil} />
                  {s.modal_perjanjian && (
                    <Angka label="Profit bersama" nilai={s.profit_bersama} />
                  )}
                  {s.modal_perjanjian && (
                    <Angka label="Bagian ASF" nilai={s.bagian_asf} />
                  )}
                </div>

                {s.modal_perjanjian && (
                  <p className="px-4 pb-3 text-caption text-ink-subtle">
                    Hidden margin {rupiah(s.hidden_margin)} — selisih modal
                    perjanjian dengan HPP sebenarnya. Tidak dijurnal: ia turunan,
                    bukan pendapatan tersendiri.
                  </p>
                )}

                <table className="w-full text-sm">
                  <thead><tr className="border-y border-line text-left text-caption text-ink-muted">
                    <th className="px-4 py-2 font-medium">Penerima</th>
                    <th className="px-4 py-2 font-medium">Jenis</th>
                    <th className="px-4 py-2 font-medium">Dasar</th>
                    <th className="px-4 py-2 text-right font-medium">Nilai</th>
                    <th className="px-4 py-2 font-medium">Transfer</th>
                  </tr></thead>
                  <tbody>
                    {s.lines.map((b) => (
                      <tr key={b.id} className="border-b border-line last:border-0">
                        <td className="px-4 py-2 text-ink">{b.payee_name}</td>
                        <td className="px-4 py-2 text-ink-muted">
                          {LABEL_JENIS[b.jenis] ?? b.jenis}
                        </td>
                        <td className="px-4 py-2 text-ink-muted">
                          {b.dasar}
                          {b.persen && ` · ${b.persen}%`}
                        </td>
                        <td className="px-4 py-2 text-right tabular-nums text-ink">
                          {rupiah(b.amount)}
                        </td>
                        <td className="px-4 py-2 text-caption text-ink-subtle">
                          {b.paid_date ? tanggal(b.paid_date) : (
                            <span className="inline-flex items-center gap-1">
                              <Lock size={12} /> belum
                            </span>
                          )}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </Card>
            ))}
          </div>
        )}

        <p className="mt-4 text-caption text-ink-subtle">
          Transfer uangnya dilakukan di halaman Disbursement, dan hanya terbuka
          untuk faktur yang sudah lunas.
        </p>
      </div>

      {/* ------------------------------------------------ form lembar baru */}
      <Modal open={open} onClose={() => setOpen(false)} title="Lembar hitung baru"
        width="max-w-3xl">
        <div className="space-y-4">
          <Field label="Faktur"
            hint="Hanya faktur yang sudah diposting — HPP riilnya diambil dari jurnal faktur itu.">
            <Select value={invoiceId}
              onChange={(e) => { setInvoiceId(e.target.value); setPratinjau(null); }}>
              <option value="">— pilih faktur —</option>
              {invoices.map((i) => (
                <option key={i.id} value={i.id}>
                  {i.number} · {rupiah(i.total)}
                </option>
              ))}
            </Select>
          </Field>

          <div className="grid gap-3 sm:grid-cols-3">
            <Field label="Modal perjanjian"
              hint="Wajib untuk dasar profit bersama / bagian ASF.">
              <Input inputMode="decimal" value={modal}
                onChange={(e) => { setModal(e.target.value); setPratinjau(null); }} />
            </Field>
            <Field label="HPP dasar komisi"
              hint="Kosongkan untuk memakai HPP riil.">
              <Input inputMode="decimal" value={hppDasar}
                onChange={(e) => { setHppDasar(e.target.value); setPratinjau(null); }} />
            </Field>
            <Field label="Pengurang per dus"
              hint="Variabel pengurang komisi — bukan ongkir aktual ke ekspedisi.">
              <Input inputMode="decimal" value={pengurang}
                onChange={(e) => { setPengurang(e.target.value); setPratinjau(null); }} />
            </Field>
          </div>

          <div>
            <div className="mb-2 flex items-center justify-between">
              <span className="text-sm font-medium text-ink">Penerima</span>
              <Button variant="secondary"
                onClick={() => setBaris((b) => [...b, { ...BARIS_KOSONG }])}>
                <Plus size={14} /> Baris
              </Button>
            </div>
            <div className="space-y-2">
              {baris.map((b, i) => (
                <div key={i} className="grid items-end gap-2 sm:grid-cols-[1.4fr_1fr_1.4fr_0.8fr_auto]">
                  <Input placeholder="Nama penerima" value={b.payee_name}
                    onChange={(e) => ubahBaris(i, { payee_name: e.target.value })} />
                  <Select value={b.jenis}
                    onChange={(e) => ubahBaris(i, { jenis: e.target.value })}>
                    {(opsi?.jenis ?? []).map((j) => (
                      <option key={j.kode} value={j.kode}>{j.kode}</option>
                    ))}
                  </Select>
                  <Select value={b.dasar}
                    onChange={(e) => ubahBaris(i, { dasar: e.target.value })}>
                    {(opsi?.dasar ?? []).map((d) => (
                      <option key={d.kode} value={d.kode}>{d.kode}</option>
                    ))}
                  </Select>
                  {b.dasar === "nominal" ? (
                    <NumCell placeholder="nominal" value={b.nominal}
                      onChange={(e) => ubahBaris(i, { nominal: e.target.value })} />
                  ) : (
                    <NumCell placeholder="%" value={b.persen}
                      onChange={(e) => ubahBaris(i, { persen: e.target.value })} />
                  )}
                  <Button variant="ghost" aria-label="Hapus baris"
                    disabled={baris.length === 1}
                    onClick={() => setBaris((x) => x.filter((_, n) => n !== i))}>
                    <Trash2 size={14} />
                  </Button>
                </div>
              ))}
            </div>
            <p className="mt-2 text-caption text-ink-subtle">
              Urutan tidak menentukan hasil: bagian ASF selalu dihitung setelah
              seluruh hak mitra selesai.
            </p>
          </div>

          {pratinjau && (
            <Card>
              <div className="grid gap-2 text-sm sm:grid-cols-4">
                <Angka label="Penjualan" nilai={pratinjau.penjualan} />
                <Angka label="HPP riil" nilai={pratinjau.hpp_riil} />
                <Angka label="Margin riil" nilai={pratinjau.margin_riil} />
                <Angka label="Total hak" nilai={pratinjau.total_hak} />
              </div>
              <table className="mt-3 w-full text-sm">
                <tbody>
                  {pratinjau.baris.map((b, i) => (
                    <tr key={i} className="border-t border-line">
                      <td className="py-1.5 text-ink">{b.payee_name}</td>
                      <td className="py-1.5 text-caption text-ink-subtle">
                        {b.keterangan_dasar}
                      </td>
                      <td className="py-1.5 text-right tabular-nums text-ink">
                        {rupiah(b.amount)}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
              {pratinjau.melebihi_margin && (
                <p className="mt-2 text-sm text-danger">
                  Total hak melebihi margin riil — periksa lagi persennya.
                </p>
              )}
            </Card>
          )}

          {formError && <p className="text-sm text-danger">{formError}</p>}

          <div className="flex justify-end gap-2">
            <Button variant="secondary" onClick={hitung}>Hitung dulu</Button>
            <Button onClick={simpan} disabled={saving}>
              {saving ? "Menyimpan…" : "Simpan draft"}
            </Button>
          </div>
          <p className="text-caption text-ink-subtle">
            Menyimpan hanya membuat draft — belum ada jurnal sampai lembar
            disetujui.
          </p>
        </div>
      </Modal>
    </>
  );
}

function Angka({ label, nilai }: { label: string; nilai: string }) {
  return (
    <div>
      <span className="block text-caption text-ink-subtle">{label}</span>
      <span className="tabular-nums text-ink">{rupiah(nilai)}</span>
    </div>
  );
}

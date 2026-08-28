"use client";
import { useEffect, useState } from "react";
import { Plus, Trash2, Check, Ban, FileSpreadsheet, Calculator,
         TriangleAlert } from "lucide-react";
import { api } from "@/lib/api";
import { rupiah, tanggal } from "@/lib/format";
import { Topbar } from "@/components/ananta/topbar";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Field, Select, Textarea, NumCell } from "@/components/ui/form";
import { Input } from "@/components/ui/input";

/**
 * Lembar Hitung — kalkulator kesepakatan bagi hasil & komisi per faktur.
 *
 * Dua hal yang membentuk tampilan halaman ini:
 *
 * 1. Lembar dibuat DRAFT dulu, baru disetujui. Menyetujui memposting beban &
 *    utang, jadi angkanya harus bisa dilihat dulu — sama seperti pratinjau di
 *    Penyesuaian Stok.
 * 2. Kolom "dari" pada tiap baris menampilkan dasar hitungnya, supaya angka
 *    seperti "6" bisa ditelusuri jadi "4% dari 150" tanpa membuka kode.
 *    Backend mengirimnya sebagai `basis_amount`.
 *
 * Pembayaran haknya TIDAK di sini — itu ada di halaman Disbursement, yang
 * hanya membuka transfer untuk faktur yang sudah lunas.
 */

type Invoice = {
  id: string; number: string; date: string; status: string;
  subtotal: string; total: string;
};
type Line = {
  id: string; urutan: number; payee_name: string; jenis: string;
  dasar: string; persen: string; nominal: string;
  basis_amount: string; amount: string; note: string | null;
  settlement_journal_id: string | null;
};
type Sheet = {
  id: string; number: string; date: string; invoice_id: string;
  status: string; penjualan: string; hpp_riil: string; jumlah_dus: string;
  modal_perjanjian: string | null; hpp_dasar_komisi: string | null;
  pengurang_per_dus: string;
  profit_bersama: string; bagian_asf: string; hidden_margin: string;
  notes: string | null; void_reason: string | null;
};
type Opsi = { kode: string; keterangan: string };
type DaftarDasar = { dasar: Opsi[]; jenis: Opsi[] };
type PratinjauBaris = {
  payee_name: string; jenis: string; dasar: string; keterangan_dasar: string;
  persen: string; nominal: string; basis_amount: string; amount: string;
};
type Pratinjau = {
  invoice_number: string; penjualan: string; hpp_riil: string;
  hpp_dasar_komisi: string; jumlah_dus: string; margin_riil: string;
  profit_bersama: string; bagian_asf: string; hidden_margin: string;
  total_hak: string; melebihi_margin: boolean; baris: PratinjauBaris[];
};
type SheetDetail = Sheet & { lines: Line[] };

type BarisInput = {
  payee_name: string; jenis: "komisi" | "bagi_hasil";
  dasar: string; persen: string; nominal: string; note: string;
};

/**
 * Daftar dasar hitung sengaja TIDAK ditulis ulang di sini — diambil dari
 * `/profit-sheets/dasar`. Daftarnya tertutup dan artinya menentukan uang
 * siapa; dua salinan pasti bergeser cepat atau lambat, dan yang bergeser
 * diam-diam biasanya penjelasannya, bukan angkanya.
 */

const LABEL_STATUS: Record<string, string> = {
  draft: "Draft", disetujui: "Disetujui", ditransfer: "Ditransfer",
  batal: "Batal",
};

const barisBaru: BarisInput = {
  payee_name: "", jenis: "komisi", dasar: "margin_riil",
  persen: "", nominal: "", note: "",
};
const today = () => new Date().toISOString().slice(0, 10);

export default function LembarHitungPage() {
  const [daftar, setDaftar] = useState<Sheet[] | null>(null);
  const [faktur, setFaktur] = useState<Invoice[]>([]);
  const [detail, setDetail] = useState<SheetDetail | null>(null);

  const [tampilForm, setTampilForm] = useState(false);
  const [invoiceId, setInvoiceId] = useState("");
  const [tgl, setTgl] = useState(today);
  const [modal, setModal] = useState("");
  const [hppKomisi, setHppKomisi] = useState("");
  const [pengurang, setPengurang] = useState("");
  const [catatan, setCatatan] = useState("");
  const [baris, setBaris] = useState<BarisInput[]>([{ ...barisBaru }]);

  const [opsi, setOpsi] = useState<DaftarDasar | null>(null);
  const [pratinjau, setPratinjau] = useState<Pratinjau | null>(null);
  const [sibuk, setSibuk] = useState(false);
  const [error, setError] = useState("");
  const [sukses, setSukses] = useState("");

  function muat() {
    api<Sheet[]>("/profit-sheets").then(setDaftar).catch((e) => setError(e.message));
  }
  useEffect(() => {
    muat();
    api<Invoice[]>("/invoices").then(setFaktur).catch(() => {});
    api<DaftarDasar>("/profit-sheets/dasar").then(setOpsi).catch(() => {});
  }, []);

  function reset() {
    setTampilForm(false);
    setInvoiceId(""); setModal(""); setHppKomisi(""); setPengurang("");
    setCatatan(""); setBaris([{ ...barisBaru }]);
  }

  /** Perubahan apa pun membatalkan pratinjau, supaya angka yang disetujui
   *  tidak pernah berbeda dari angka yang disimpan. */
  function ubah(i: number, patch: Partial<BarisInput>) {
    setBaris((b) => b.map((r, n) => (n === i ? { ...r, ...patch } : r)));
    setPratinjau(null);
  }

  const butuhModal = baris.some(
    (b) => b.dasar === "profit_bersama" || b.dasar === "bagian_asf");
  const butuhHppKomisi = baris.some((b) => b.dasar === "margin_komisi");

  /** Isi yang dikirim ke server — sengaja satu, dipakai pratinjau & simpan. */
  function badan() {
    return {
      invoice_id: invoiceId,
      modal_perjanjian: modal === "" ? null : modal,
      hpp_dasar_komisi: hppKomisi === "" ? null : hppKomisi,
      pengurang_per_dus: pengurang || "0",
      lines: baris
        .filter((b) => b.payee_name.trim())
        .map((b) => ({
          payee_name: b.payee_name, jenis: b.jenis, dasar: b.dasar,
          persen: b.persen || "0", nominal: b.nominal || "0",
          note: b.note || null,
        })),
    };
  }

  async function hitung() {
    setError(""); setSukses(""); setSibuk(true);
    try {
      setPratinjau(await api<Pratinjau>("/profit-sheets/pratinjau", {
        method: "POST", body: JSON.stringify(badan()),
      }));
    } catch (e) {
      setPratinjau(null);
      setError(e instanceof Error ? e.message : String(e));
    } finally { setSibuk(false); }
  }

  async function simpan() {
    setError(""); setSukses(""); setSibuk(true);
    try {
      const s = await api<SheetDetail>("/profit-sheets", {
        method: "POST",
        body: JSON.stringify({ ...badan(), date: tgl, notes: catatan || null }),
      });
      setSukses(`Lembar ${s.number} dibuat sebagai draft. Periksa angkanya, lalu setujui.`);
      setDetail(s);
      reset();
      muat();
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally { setSibuk(false); }
  }

  async function bukaDetail(id: string) {
    setError("");
    try { setDetail(await api<SheetDetail>(`/profit-sheets/${id}`)); }
    catch (e) { setError(e instanceof Error ? e.message : String(e)); }
  }

  async function setujui(id: string) {
    setError(""); setSukses(""); setSibuk(true);
    try {
      await api(`/profit-sheets/${id}/approve`, {
        method: "POST", body: JSON.stringify({ date: today() }),
      });
      setSukses("Lembar disetujui — beban & utangnya sudah masuk buku.");
      await bukaDetail(id); muat();
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally { setSibuk(false); }
  }

  async function batalkan(id: string) {
    const alasan = window.prompt(
      "Batalkan lembar ini dan balik jurnalnya?\n\n" +
      "Dipakai untuk faktur yang tidak akan pernah lunas — tanpa ini utangnya " +
      "menumpuk selamanya. Tulis alasannya:");
    if (alasan === null) return;
    setError(""); setSukses(""); setSibuk(true);
    try {
      await api(`/profit-sheets/${id}/void`, {
        method: "POST",
        body: JSON.stringify({ date: today(), reason: alasan || null }),
      });
      setSukses("Lembar dibatalkan, jurnalnya sudah dibalik.");
      await bukaDetail(id); muat();
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally { setSibuk(false); }
  }

  const nomorFaktur = (id: string) =>
    faktur.find((f) => f.id === id)?.number ?? "—";

  return (
    <>
      <Topbar title="Lembar Hitung" />
      <div className="space-y-6 p-6">
        <Card>
          <div className="flex flex-wrap items-start justify-between gap-3">
            <div>
              <p className="text-sm text-ink">
                Kalkulator kesepakatan bagi hasil &amp; komisi yang menempel di
                satu faktur.
              </p>
              <p className="mt-1 text-caption text-ink-subtle">
                Lembar tidak pernah mengubah Pendapatan, HPP, atau Persediaan —
                yang dijurnal hanya hasilnya, sebagai beban dan utang. Pembayaran
                haknya dilakukan di halaman Disbursement setelah faktur lunas.
              </p>
            </div>
            {!tampilForm && (
              <Button onClick={() => { setTampilForm(true); setSukses(""); }}>
                <Plus size={16} /> Buat lembar
              </Button>
            )}
          </div>
          {error && <p className="mt-3 text-sm text-danger">{error}</p>}
          {sukses && <p className="mt-3 text-sm text-primary">{sukses}</p>}
        </Card>

        {/* ------------------------------------------------------- form baru */}
        {tampilForm && (
          <Card>
            <h2 className="font-display text-lg font-semibold text-ink">
              Lembar baru
            </h2>

            <div className="mt-4 grid gap-4 md:grid-cols-4">
              <Field label="Faktur">
                <Select value={invoiceId}
                        onChange={(e) => setInvoiceId(e.target.value)}>
                  <option value="">— pilih faktur —</option>
                  {faktur.map((f) => (
                    <option key={f.id} value={f.id}>
                      {f.number} · {rupiah(f.total)}
                    </option>
                  ))}
                </Select>
              </Field>
              <Field label="Tanggal">
                <Input type="date" value={tgl}
                       onChange={(e) => setTgl(e.target.value)} />
              </Field>
              <Field
                label="Modal perjanjian"
                hint={butuhModal
                  ? "Wajib — dipakai baris profit bersama / bagian ASF."
                  : "Modal “seolah-olah” yang disepakati mitra."}
              >
                <NumCell value={modal} placeholder="kosongkan bila tak dipakai"
                         onChange={(e) => setModal(e.target.value)} />
              </Field>
              <Field
                label="HPP dasar komisi"
                hint={butuhHppKomisi
                  ? "Wajib — dipakai baris margin versi kesepakatan."
                  : "Tidak menggeser HPP di pembukuan."}
              >
                <NumCell value={hppKomisi} placeholder="kosongkan bila tak dipakai"
                         onChange={(e) => setHppKomisi(e.target.value)} />
              </Field>
            </div>

            <div className="mt-4 grid gap-4 md:grid-cols-2">
              <Field label="Pengurang per dus"
                     hint="Mis. Rp50.000/dus pada skema Rusdi. Bukan ongkir riil dan tidak pernah masuk jurnal.">
                <NumCell value={pengurang} placeholder="0"
                         onChange={(e) => setPengurang(e.target.value)} />
              </Field>
              <Field label="Catatan">
                <Textarea rows={2} value={catatan}
                          onChange={(e) => setCatatan(e.target.value)} />
              </Field>
            </div>

            <div className="mt-4 overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-line text-left text-caption text-ink-muted">
                    <th className="py-2 pr-2 font-medium">Penerima</th>
                    <th className="w-40 px-2 py-2 font-medium">Sifat</th>
                    <th className="w-64 px-2 py-2 font-medium">Dihitung dari</th>
                    <th className="w-24 px-2 py-2 text-right font-medium">%</th>
                    <th className="w-32 px-2 py-2 text-right font-medium">Nominal</th>
                    <th className="w-10" />
                  </tr>
                </thead>
                <tbody>
                  {baris.map((b, i) => {
                    const d = opsi?.dasar.find((x) => x.kode === b.dasar);
                    return (
                      <tr key={i} className="border-b border-line/60 align-top">
                        <td className="py-2 pr-2">
                          <Input value={b.payee_name} placeholder="mis. Andre"
                                 onChange={(e) => ubah(i, { payee_name: e.target.value })} />
                        </td>
                        <td className="px-2 py-2">
                          <Select value={b.jenis}
                                  onChange={(e) => ubah(i, { jenis: e.target.value as BarisInput["jenis"] })}>
                            {(opsi?.jenis ?? []).map((x) => (
                              <option key={x.kode} value={x.kode}>
                                {x.keterangan}
                              </option>
                            ))}
                          </Select>
                        </td>
                        <td className="px-2 py-2">
                          <Select value={b.dasar}
                                  onChange={(e) => ubah(i, { dasar: e.target.value })}>
                            {(opsi?.dasar ?? []).map((x) => (
                              <option key={x.kode} value={x.kode}>{x.kode}</option>
                            ))}
                          </Select>
                          {d && (
                            <p className="mt-1 text-caption text-ink-subtle">
                              {d.keterangan}
                            </p>
                          )}
                        </td>
                        <td className="px-2 py-2">
                          <NumCell value={b.persen} placeholder="0"
                                   disabled={b.dasar === "nominal"}
                                   onChange={(e) => ubah(i, { persen: e.target.value })} />
                        </td>
                        <td className="px-2 py-2">
                          <NumCell value={b.nominal} placeholder="0"
                                   disabled={b.dasar !== "nominal"}
                                   onChange={(e) => ubah(i, { nominal: e.target.value })} />
                        </td>
                        <td className="py-2">
                          <button
                            type="button"
                            onClick={() => setBaris((x) => x.length === 1 ? x : x.filter((_, n) => n !== i))}
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

            <p className="mt-3 text-caption text-ink-subtle">
              Baris “Bagian ASF” selalu dihitung <b>setelah</b> seluruh hak mitra,
              berapa pun urutan ketiknya — bagian ASF adalah sisa setelah mitra
              mengambil haknya.
            </p>

            <div className="mt-4 flex flex-wrap gap-2">
              <Button variant="secondary"
                      onClick={() => setBaris((b) => [...b, { ...barisBaru }])}>
                <Plus size={16} /> Tambah baris
              </Button>
              <Button variant="secondary" onClick={hitung}
                      disabled={sibuk || !invoiceId || !baris.some((b) => b.payee_name.trim())}>
                <Calculator size={16} /> Hitung
              </Button>
              <Button onClick={simpan}
                      disabled={sibuk || !invoiceId || !baris.some((b) => b.payee_name.trim())}>
                Simpan sebagai draft
              </Button>
              <Button variant="ghost" onClick={reset} disabled={sibuk}>
                Batal
              </Button>
            </div>

            {pratinjau && (
              <div className="mt-4 rounded-[var(--radius-card)] border border-line p-4">
                <p className="text-sm text-ink">
                  Hasil hitung untuk faktur <b>{pratinjau.invoice_number}</b> —
                  belum ada yang disimpan.
                </p>

                {pratinjau.melebihi_margin && (
                  <p className="mt-3 flex gap-2 rounded-[var(--radius-card)] border border-warning bg-surface-sunken p-3 text-sm text-ink">
                    <TriangleAlert size={16} className="mt-0.5 shrink-0 text-warning" />
                    <span>
                      Total hak {rupiah(pratinjau.total_hak)} melebihi margin
                      riil {rupiah(pratinjau.margin_riil)} — menyimpan akan
                      ditolak. Angkanya tetap ditampilkan supaya terlihat
                      seberapa jauh melesetnya.
                    </span>
                  </p>
                )}

                <div className="mt-3 grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
                  {[
                    ["Penjualan", pratinjau.penjualan],
                    ["HPP riil", pratinjau.hpp_riil],
                    ["Margin riil", pratinjau.margin_riil],
                    ["Profit bersama", pratinjau.profit_bersama],
                    ["Bagian ASF", pratinjau.bagian_asf],
                    ["Hidden margin", pratinjau.hidden_margin],
                    ["Total hak", pratinjau.total_hak],
                  ].map(([label, nilai]) => (
                    <div key={label} className="rounded-[var(--radius-card)] bg-surface-sunken p-3">
                      <p className="text-caption text-ink-subtle">{label}</p>
                      <p className="mt-0.5 tabular-nums text-ink">{rupiah(nilai)}</p>
                    </div>
                  ))}
                </div>

                <table className="mt-4 w-full text-sm">
                  <thead>
                    <tr className="border-b border-line text-left text-caption text-ink-muted">
                      <th className="py-2 pr-2 font-medium">Penerima</th>
                      <th className="px-2 py-2 font-medium">Dihitung dari</th>
                      <th className="px-2 py-2 text-right font-medium">Hak</th>
                    </tr>
                  </thead>
                  <tbody>
                    {pratinjau.baris.map((b, i) => (
                      <tr key={i} className="border-b border-line/60">
                        <td className="py-2 pr-2 text-ink">{b.payee_name}</td>
                        <td className="px-2 py-2 text-ink-muted">
                          {b.dasar === "nominal"
                            ? b.keterangan_dasar
                            : `${Number(b.persen)}% dari ${rupiah(b.basis_amount)}`}
                          <span className="ml-1 text-caption text-ink-subtle">
                            ({b.keterangan_dasar})
                          </span>
                        </td>
                        <td className="px-2 py-2 text-right font-medium tabular-nums text-ink">
                          {rupiah(b.amount)}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </Card>
        )}

        {/* ---------------------------------------------------------- detail */}
        {detail && (
          <Card>
            <div className="flex flex-wrap items-start justify-between gap-3">
              <div>
                <h2 className="font-display text-lg font-semibold text-ink">
                  {detail.number}
                  <span className="ml-2 rounded-[var(--radius-badge)] bg-surface-sunken px-2 py-0.5 text-caption font-normal text-ink-muted">
                    {LABEL_STATUS[detail.status] ?? detail.status}
                  </span>
                </h2>
                <p className="mt-1 text-sm text-ink-muted">
                  Faktur {nomorFaktur(detail.invoice_id)} · {tanggal(detail.date)}
                </p>
              </div>
              <div className="flex gap-2">
                {detail.status === "draft" && (
                  <Button onClick={() => setujui(detail.id)} disabled={sibuk}>
                    <Check size={16} /> Setujui
                  </Button>
                )}
                {detail.status !== "batal" && (
                  <Button variant="secondary" onClick={() => batalkan(detail.id)}
                          disabled={sibuk}>
                    <Ban size={16} /> Batalkan
                  </Button>
                )}
              </div>
            </div>

            <div className="mt-4 grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
              {[
                ["Penjualan", rupiah(detail.penjualan)],
                ["HPP riil", rupiah(detail.hpp_riil)],
                ["Jumlah dus", Number(detail.jumlah_dus).toLocaleString("id-ID")],
                ["Modal perjanjian",
                 detail.modal_perjanjian ? rupiah(detail.modal_perjanjian) : "—"],
              ].map(([label, nilai]) => (
                <div key={label} className="rounded-[var(--radius-card)] border border-line p-3">
                  <p className="text-caption text-ink-subtle">{label}</p>
                  <p className="mt-0.5 tabular-nums text-ink">{nilai}</p>
                </div>
              ))}
            </div>

            {detail.modal_perjanjian && (
              <p className="mt-3 text-caption text-ink-subtle">
                Profit bersama{" "}
                <b className="tabular-nums">{rupiah(detail.profit_bersama)}</b>,
                bagian ASF{" "}
                <b className="tabular-nums">{rupiah(detail.bagian_asf)}</b>,
                hidden margin{" "}
                <b className="tabular-nums">{rupiah(detail.hidden_margin)}</b>{" "}
                — hak internal penuh, sengaja <b>tidak</b> dijurnal karena ia
                turunan; menjurnalnya membuat laba dihitung dua kali.
              </p>
            )}

            <div className="mt-4 overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-line text-left text-caption text-ink-muted">
                    <th className="py-2 pr-2 font-medium">Penerima</th>
                    <th className="px-2 py-2 font-medium">Sifat</th>
                    <th className="px-2 py-2 font-medium">Dihitung dari</th>
                    <th className="px-2 py-2 text-right font-medium">Hak</th>
                    <th className="px-2 py-2 font-medium">Status</th>
                  </tr>
                </thead>
                <tbody>
                  {detail.lines.map((l) => (
                    <tr key={l.id} className="border-b border-line/60">
                      <td className="py-2 pr-2 text-ink">{l.payee_name}</td>
                      <td className="px-2 py-2 text-ink-muted">
                        {l.jenis === "komisi" ? "Komisi pihak luar" : "Hak mitra"}
                      </td>
                      <td className="px-2 py-2 text-ink-muted">
                        {l.dasar === "nominal"
                          ? "nominal tetap"
                          : `${Number(l.persen)}% dari ${rupiah(l.basis_amount)}`}
                      </td>
                      <td className="px-2 py-2 text-right font-medium tabular-nums text-ink">
                        {rupiah(l.amount)}
                      </td>
                      <td className="px-2 py-2 text-caption text-ink-subtle">
                        {l.settlement_journal_id ? "sudah ditransfer" : "belum ditransfer"}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            {detail.void_reason && (
              <p className="mt-3 text-sm text-ink-muted">
                Alasan pembatalan: {detail.void_reason}
              </p>
            )}
          </Card>
        )}

        {/* --------------------------------------------------------- daftar */}
        <Card className="overflow-hidden p-0">
          <h2 className="px-4 pt-4 font-display text-lg font-semibold text-ink">
            Daftar lembar
          </h2>
          {daftar && daftar.length === 0 && (
            <p className="flex items-center gap-2 px-4 pb-4 pt-2 text-sm text-ink-muted">
              <FileSpreadsheet size={16} /> Belum ada lembar hitung.
            </p>
          )}
          {daftar && daftar.length > 0 && (
            <table className="mt-3 w-full text-sm">
              <thead>
                <tr className="border-y border-line text-left text-caption text-ink-muted">
                  <th className="px-4 py-3 font-medium">Nomor</th>
                  <th className="px-4 py-3 font-medium">Tanggal</th>
                  <th className="px-4 py-3 font-medium">Faktur</th>
                  <th className="px-4 py-3 font-medium">Status</th>
                  <th className="px-4 py-3 text-right font-medium">Penjualan</th>
                  <th className="px-4 py-3" />
                </tr>
              </thead>
              <tbody>
                {daftar.map((s) => (
                  <tr key={s.id} className="border-b border-line/60">
                    <td className="px-4 py-3 font-medium text-ink">{s.number}</td>
                    <td className="px-4 py-3 text-ink-muted">{tanggal(s.date)}</td>
                    <td className="px-4 py-3 text-ink-muted">
                      {nomorFaktur(s.invoice_id)}
                    </td>
                    <td className="px-4 py-3 text-ink-muted">
                      {LABEL_STATUS[s.status] ?? s.status}
                    </td>
                    <td className="px-4 py-3 text-right tabular-nums">
                      {rupiah(s.penjualan)}
                    </td>
                    <td className="px-4 py-3 text-right">
                      <Button variant="ghost" onClick={() => bukaDetail(s.id)}>
                        Lihat
                      </Button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </Card>
      </div>
    </>
  );
}

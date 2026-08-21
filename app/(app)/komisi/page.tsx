"use client";
import { useEffect, useState, type FormEvent } from "react";
import { Plus, Settings2, X } from "lucide-react";
import { api } from "@/lib/api";
import { rupiah, tanggal } from "@/lib/format";
import { Topbar } from "@/components/ananta/topbar";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Modal } from "@/components/ui/modal";
import { Field, Select, Textarea } from "@/components/ui/form";

type Komisi = {
  id: string; number: string; date: string; invoice_id: string;
  payee_name: string; basis: string; amount: string; status: string;
  paid_date: string | null;
};
type Invoice = { id: string; number: string; status: string; total: string };
type Saran = {
  invoice_number: string; omzet: string; modal: string; margin: string;
  saran_5_persen_margin: string;
};
type Skema = { id: string; name: string; type: string; value: string; ongkir_per_dus: string | null };
type Langkah = { label: string; nilai: string };

const LABEL_TIPE: Record<string, string> = {
  nominal: "flat", per_botol: "per botol", persen_margin: "% margin",
  persen_omzet: "% omzet", persen_margin_min_ongkir: "% margin \u2212 ongkir",
  manual: "kasus khusus",
};

const today = () => new Date().toISOString().slice(0, 10);
const KOSONG = { invoice_id: "", payee_name: "", amount: "", basis: "nominal", scheme_id: "", note: "" };

/** Hanya faktur yang barangnya sudah keluar yang boleh dikomisikan. */
const FAKTUR_SAH = new Set(["posted", "paid", "overdue"]);

export default function KomisiPage() {
  const [items, setItems] = useState<Komisi[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [invoices, setInvoices] = useState<Invoice[]>([]);

  const [open, setOpen] = useState(false);
  const [form, setForm] = useState({ ...KOSONG });
  const [saran, setSaran] = useState<Saran | null>(null);
  const [skema, setSkema] = useState<Skema[]>([]);
  const [saving, setSaving] = useState(false);
  const [formError, setFormError] = useState<string | null>(null);

  const [kelola, setKelola] = useState(false);
  const [skemaBaru, setSkemaBaru] = useState({ name: "", type: "nominal", value: "", ongkir_per_dus: "" });
  const [langkah, setLangkah] = useState<Langkah[]>([]);
  const [skemaError, setSkemaError] = useState<string | null>(null);

  const [bayar, setBayar] = useState<Komisi | null>(null);
  const [akun, setAkun] = useState("1-1000");
  const [bayarError, setBayarError] = useState<string | null>(null);
  const [paying, setPaying] = useState(false);

  function muat() {
    api<Komisi[]>("/commissions").then(setItems).catch((e) => setError(e.message));
  }
  function muatSkema() {
  }
  useEffect(() => { muat(); muatSkema(); }, []);

  async function simpanSkema() {
    setSkemaError(null);
    if (!skemaBaru.name.trim()) return setSkemaError("Beri nama skemanya.");
    // `manual` memang tidak punya angka — ia cuma menandai "diketik manusia".
    if (skemaBaru.type !== "manual" && !(Number(skemaBaru.value) > 0)) {
      return setSkemaError("Isi nilainya, atau pilih tipe Kasus khusus.");
    }
    if (skemaBaru.type === "persen_margin_min_ongkir"
        && !(Number(skemaBaru.ongkir_per_dus) > 0)) {
      return setSkemaError("Isi tarif ongkir per dus-nya.");
    }
    try {
      await api("/commissions/schemes", {
        method: "POST",
        body: JSON.stringify({
          name: skemaBaru.name.trim(), type: skemaBaru.type,
          value: skemaBaru.type === "manual" ? "0" : skemaBaru.value,
          ongkir_per_dus: skemaBaru.type === "persen_margin_min_ongkir"
            ? skemaBaru.ongkir_per_dus : null,
        }),
      });
      setSkemaBaru({ name: "", type: "nominal", value: "", ongkir_per_dus: "" });
      muatSkema();
    } catch (err) {
      setSkemaError(err instanceof Error ? err.message : "Gagal menyimpan skema.");
    }
  }

  async function nonaktifkanSkema(id: string) {
    try {
      await api(`/commissions/schemes/${id}`, { method: "DELETE" });
      muatSkema();
    } catch { /* abaikan */ }
  }

  function buka() {
    setFormError(null); setSaran(null); setLangkah([]); setForm({ ...KOSONG }); setOpen(true);
    api<Invoice[]>("/invoices")
      .then((all) => setInvoices(all.filter((i) => FAKTUR_SAH.has(i.status))))
      .catch(() => {});
  }

  function set<K extends keyof typeof form>(k: K, v: string) {
    setForm((f) => ({ ...f, [k]: v }));
  }

  /** Ambil omzet & margin faktur sebagai bahan pertimbangan — tidak mengikat. */
  function pilihFaktur(id: string) {
    set("invoice_id", id);
    setSaran(null);
    // Rincian lama milik faktur sebelumnya — buang, jangan sampai tertinggal
    // di layar dan dikira menjelaskan faktur yang baru.
    setLangkah([]);
    if (!id) return;
    api<Saran>(`/commissions/saran?invoice_id=${id}`).then(setSaran).catch(() => {});
  }

  /** Hitung nilai menurut skema. `manual` sengaja tidak menghitung apa pun. */
  async function pilihSkema(id: string) {
    set("scheme_id", id);
    setLangkah([]);
    if (!id || !form.invoice_id) return;
    try {
      const r = await api<{ amount: string; manual: boolean; langkah: Langkah[] }>(
        `/commissions/schemes/${id}/hitung?invoice_id=${form.invoice_id}`);
      if (!r.manual) { set("amount", r.amount); setLangkah(r.langkah ?? []); }
    } catch { /* biarkan user mengetik sendiri */ }
  }

  async function simpan(e: FormEvent) {
    e.preventDefault();
    setFormError(null);
    if (!form.invoice_id) return setFormError("Pilih faktur dasarnya dulu.");
    if (!(Number(form.amount) > 0)) return setFormError("Nilai komisi harus lebih dari 0.");
    setSaving(true);
    try {
      await api("/commissions", {
        method: "POST",
        body: JSON.stringify({
          date: today(),
          invoice_id: form.invoice_id,
          payee_name: form.payee_name.trim(),
          amount: form.amount,
          basis: form.basis,
          scheme_id: form.scheme_id || null,
          note: form.note || null,
        }),
      });
      setOpen(false); muat();
    } catch (err) {
      setFormError(err instanceof Error ? err.message : "Gagal menyimpan.");
    } finally { setSaving(false); }
  }

  async function bayarKomisi(e: FormEvent) {
    e.preventDefault();
    if (!bayar) return;
    setBayarError(null); setPaying(true);
    try {
      await api(`/commissions/${bayar.id}/pay`, {
        method: "POST",
        body: JSON.stringify({ date: today(), paid_account_code: akun }),
      });
      setBayar(null); muat();
    } catch (err) {
      setBayarError(err instanceof Error ? err.message : "Gagal membayar.");
    } finally { setPaying(false); }
  }

  const terutang = (items ?? [])
    .filter((k) => k.status === "terutang")
    .reduce((s, k) => s + Number(k.amount), 0);

  return (
    <>
      <Topbar title="Komisi Penjualan" />
      <div className="p-6">
        <Card className="mb-4">
          <p className="text-sm text-ink">
            Komisi adalah kesepakatan <b>internal</b> — tidak pernah muncul di faktur
            customer, dan harga di faktur tetap harga sebenarnya.
          </p>
          <p className="mt-1 text-caption text-ink-subtle">
            Nilainya diketik per kasus. Bebannya masuk Laba Rugi (akun 6-1100 Beban
            Komisi) <b>saat dicatat</b>; membayar hanya menutup Utang Komisi di neraca.
          </p>
        </Card>

        <div className="mb-4 flex items-center justify-between">
          <p className="text-sm text-ink-muted">
            Belum dibayar: <b className="tabular-nums text-ink">{rupiah(terutang)}</b>
            <span className="text-ink-subtle"> — utang komisi di neraca</span>
          </p>
          <div className="flex gap-2">
            <Button variant="secondary" onClick={() => { setSkemaError(null); setKelola(true); }}>
              <Settings2 size={16} /> Skema
            </Button>
            <Button onClick={buka}><Plus size={16} /> Catat Komisi</Button>
          </div>
        </div>

        {error && <Card><p className="text-sm text-danger">{error}</p></Card>}
        {items?.length === 0 && (
          <Card className="text-center">
            <p className="text-ink">Belum ada komisi tercatat.</p>
            <p className="mt-1 text-sm text-ink-muted">
              Catat komisi atas faktur yang barangnya sudah keluar.
            </p>
          </Card>
        )}

        {items && items.length > 0 && (
          <Card className="overflow-hidden p-0">
            <table className="w-full text-sm">
              <thead><tr className="border-b border-line text-left text-caption text-ink-muted">
                <th className="px-4 py-3 font-medium">No.</th>
                <th className="px-4 py-3 font-medium">Tanggal</th>
                <th className="px-4 py-3 font-medium">Penerima</th>
                <th className="px-4 py-3 text-right font-medium">Nilai</th>
                <th className="px-4 py-3 font-medium">Status</th>
                <th className="px-4 py-3" />
              </tr></thead>
              <tbody>
                {items.map((k) => (
                  <tr key={k.id} className="border-b border-line last:border-0 hover:bg-surface-sunken">
                    <td className="px-4 py-3 text-ink">{k.number}</td>
                    <td className="px-4 py-3 text-ink-muted">{tanggal(k.date)}</td>
                    <td className="px-4 py-3 text-ink">{k.payee_name}</td>
                    <td className="px-4 py-3 text-right tabular-nums text-ink">{rupiah(k.amount)}</td>
                    <td className="px-4 py-3">
                      {k.status === "dibayar" && (
                        <span className="text-ink-muted">
                          Dibayar {k.paid_date ? tanggal(k.paid_date) : ""}
                        </span>
                      )}
                      {k.status === "terutang" && <span className="text-warning">Belum dibayar</span>}
                      {k.status === "void" && <span className="text-ink-subtle">Dibatalkan</span>}
                    </td>
                    <td className="px-4 py-3 text-right">
                      {k.status === "terutang" && (
                        <Button variant="secondary" onClick={() => { setBayarError(null); setBayar(k); }}>
                          Bayar
                        </Button>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </Card>
        )}
      </div>

      <Modal open={open} onClose={() => setOpen(false)} title="Catat Komisi">
        <form onSubmit={simpan} className="space-y-4">
          <Field label="Faktur dasar" hint="Hanya faktur yang barangnya sudah keluar">
            <Select value={form.invoice_id} onChange={(e) => pilihFaktur(e.target.value)} required>
              <option value="">— pilih faktur —</option>
              {invoices.map((i) => (
                <option key={i.id} value={i.id}>{i.number} · {rupiah(i.total)}</option>
              ))}
            </Select>
          </Field>

          {saran && (
            <div className="rounded-[var(--radius-card)] bg-surface-sunken p-3">
              <p className="text-caption text-ink-subtle">
                Sekadar bahan pertimbangan — nilai akhirnya tetap kamu yang tentukan:
              </p>
              <p className="mt-1 text-sm tabular-nums text-ink">
                Omzet {rupiah(saran.omzet)} · Modal {rupiah(saran.modal)} ·
                Margin <b>{rupiah(saran.margin)}</b>
              </p>
              <button type="button"
                className="mt-2 text-caption text-primary underline"
                onClick={() => { set("amount", saran.saran_5_persen_margin); set("basis", "persen_margin"); }}>
                Isi dengan 5% dari margin ({rupiah(saran.saran_5_persen_margin)})
              </button>
            </div>
          )}

          {skema.length > 0 && (
            <Field label="Skema komisi" hint="Mengisi nominal otomatis — tetap bisa ditimpa">
              <Select value={form.scheme_id} onChange={(e) => pilihSkema(e.target.value)}>
                <option value="">— tanpa skema, ketik sendiri —</option>
                {skema.map((s) => (
                  <option key={s.id} value={s.id}>
                    {s.name} ({LABEL_TIPE[s.type] ?? s.type})
                  </option>
                ))}
              </Select>
            </Field>
          )}

          {langkah.length > 0 && (
            <div className="rounded-[var(--radius-card)] bg-surface-sunken p-3">
              <p className="text-caption text-ink-subtle">Cara angkanya didapat:</p>
              <div className="mt-1 space-y-0.5">
                {langkah.map((l, i) => (
                  <div key={i} className="flex justify-between text-caption">
                    <span className="text-ink-muted">{l.label}</span>
                    <span className="tabular-nums text-ink">{l.nilai}</span>
                  </div>
                ))}
              </div>
            </div>
          )}

          <div className="grid grid-cols-2 gap-4">
            <Field label="Penerima komisi">
              <Input value={form.payee_name} onChange={(e) => set("payee_name", e.target.value)}
                required placeholder="nama sales / perantara" />
            </Field>
            <Field label="Nilai komisi (Rp)" hint="Diketik per kasus">
              <Input type="number" min={0} value={form.amount}
                onChange={(e) => set("amount", e.target.value)} required />
            </Field>
          </div>

          <Field label="Dasar kesepakatan" hint="Catatan saja — tidak dipakai menghitung ulang">
            <Select value={form.basis} onChange={(e) => set("basis", e.target.value)}>
              <option value="nominal">Nominal disepakati</option>
              <option value="persen_margin">Persen dari margin</option>
              <option value="persen_omzet">Persen dari omzet</option>
            </Select>
          </Field>

          <Field label="Catatan">
            <Textarea rows={2} value={form.note} onChange={(e) => set("note", e.target.value)}
              placeholder="opsional — konteks kesepakatannya" />
          </Field>

          <p className="text-caption text-ink-subtle">
            Menyimpan langsung membuat jurnal: Debit <b>Beban Komisi</b>, Kredit
            <b> Utang Komisi</b>. Bebannya diakui sekarang, bukan nanti saat dibayar.
          </p>

          {formError && <p className="text-sm text-danger">{formError}</p>}
          <div className="flex justify-end gap-2 pt-2">
            <Button type="button" variant="secondary" onClick={() => setOpen(false)}>Batal</Button>
            <Button type="submit" disabled={saving}>{saving ? "Menyimpan…" : "Simpan"}</Button>
          </div>
        </form>
      </Modal>

      <Modal open={kelola} onClose={() => setKelola(false)} title="Skema Komisi">
        <div className="space-y-4">
          <p className="text-caption text-ink-subtle">
            Skema hanya <b>mengisi</b> nominal saat mencatat komisi — nilai akhirnya
            selalu bisa ditimpa. Pilih <b>Kasus khusus</b> untuk kesepakatan yang
            tidak mengikuti pola apa pun: ia tidak menghitung apa-apa, angkanya
            diketik sendiri.
          </p>

          {skema.length > 0 && (
            <div className="divide-y divide-line rounded-[var(--radius-card)] border border-line">
              {skema.map((sk) => (
                <div key={sk.id} className="flex items-center justify-between px-3 py-2">
                  <div>
                    <p className="text-sm text-ink">{sk.name}</p>
                    <p className="text-caption text-ink-subtle">
                      {LABEL_TIPE[sk.type] ?? sk.type}
                      {sk.type !== "manual" && ` · ${
                        sk.type.startsWith("persen") ? `${sk.value}%` : rupiah(sk.value)}`}
                    </p>
                  </div>
                  <button type="button" onClick={() => nonaktifkanSkema(sk.id)}
                    aria-label="Nonaktifkan skema"
                    className="text-ink-subtle hover:text-danger">
                    <X size={16} />
                  </button>
                </div>
              ))}
            </div>
          )}
          {skema.length === 0 && (
            <p className="text-sm text-ink-muted">Belum ada skema.</p>
          )}

          <div className="space-y-3 rounded-[var(--radius-card)] bg-surface-sunken p-3">
            <Field label="Nama skema">
              <Input value={skemaBaru.name} placeholder="mis. Flat 50rb per faktur"
                onChange={(e) => setSkemaBaru((f) => ({ ...f, name: e.target.value }))} />
            </Field>
            <div className="grid grid-cols-2 gap-3">
              <Field label="Cara hitung">
                <Select value={skemaBaru.type}
                  onChange={(e) => setSkemaBaru((f) => ({ ...f, type: e.target.value }))}>
                  <option value="nominal">Nominal flat (Rp)</option>
                  <option value="per_botol">Per botol terjual (Rp)</option>
                  <option value="persen_margin">Persen dari margin (%)</option>
                  <option value="persen_omzet">Persen dari omzet (%)</option>
                  <option value="persen_margin_min_ongkir">Persen dari margin setelah potong ongkir (%)</option>
                  <option value="manual">Kasus khusus — ketik sendiri</option>
                </Select>
              </Field>
              <Field label={skemaBaru.type.startsWith("persen") ? "Persen" : "Nilai (Rp)"}>
                <Input type="number" min={0} value={skemaBaru.value}
                  disabled={skemaBaru.type === "manual"}
                  onChange={(e) => setSkemaBaru((f) => ({ ...f, value: e.target.value }))} />
              </Field>
            </div>
            {skemaBaru.type === "persen_margin_min_ongkir" && (
              <Field label="Tarif ongkir per dus (Rp)"
                hint="Tarif KESEPAKATAN dengan sales — bukan ongkir yang dibayar ke ekspedisi">
                <Input type="number" min={0} value={skemaBaru.ongkir_per_dus}
                  onChange={(e) => setSkemaBaru((f) => ({ ...f, ongkir_per_dus: e.target.value }))} />
              </Field>
            )}
            {skemaError && <p className="text-sm text-danger">{skemaError}</p>}
            <div className="flex justify-end">
              <Button type="button" onClick={simpanSkema}><Plus size={16} /> Tambah Skema</Button>
            </div>
          </div>

          <p className="text-caption text-ink-subtle">
            Menutup skema tidak menghapusnya — komisi lama tetap menunjuk ke sana,
            dan tarif yang dipakai sudah disalin ke tiap baris komisi.
          </p>
        </div>
      </Modal>

      <Modal open={!!bayar} onClose={() => setBayar(null)} title="Bayar Komisi">
        <form onSubmit={bayarKomisi} className="space-y-4">
          <p className="text-sm text-ink">
            {bayar?.payee_name} · <b className="tabular-nums">{rupiah(bayar?.amount ?? 0)}</b>
          </p>
          <Field label="Dibayar dari">
            <Select value={akun} onChange={(e) => setAkun(e.target.value)}>
              <option value="1-1000">Kas</option>
              <option value="1-1100">Bank</option>
              <option value="1-1110">Bank BCA - Silo</option>
              <option value="1-1120">Bank OCBC - Silo</option>
            </Select>
          </Field>
          <p className="text-caption text-ink-subtle">
            Jurnal yang dibuat: Debit <b>Utang Komisi (2-1600)</b>, Kredit kas/bank di
            atas. Ini pelunasan — bebannya sudah diakui waktu komisi dicatat, jadi
            Laba Rugi tidak berubah.
          </p>
          {bayarError && <p className="text-sm text-danger">{bayarError}</p>}
          <div className="flex justify-end gap-2 pt-2">
            <Button type="button" variant="secondary" onClick={() => setBayar(null)}>Batal</Button>
            <Button type="submit" disabled={paying}>{paying ? "Memproses…" : "Bayar & Jurnal"}</Button>
          </div>
        </form>
      </Modal>
    </>
  );
}

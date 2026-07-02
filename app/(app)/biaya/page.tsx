"use client";
import { useEffect, useState, type FormEvent } from "react";
import { Plus, Wallet } from "lucide-react";
import { api } from "@/lib/api";
import { rupiah, tanggal } from "@/lib/format";
import { Topbar } from "@/components/ananta/topbar";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Modal } from "@/components/ui/modal";
import { Field, Select } from "@/components/ui/form";

type Expense = { id: string; number: string; date: string; category: string; description: string; amount: string };
type Loan = { id: string; number: string; employee_name: string; date: string; amount: string; repaid_total: string; status: string };
type Account = { id: string; code: string; name: string; type: string };

const today = () => new Date().toISOString().slice(0, 10);
const CASH_OPTS = [
  { code: "1-1000", label: "Kas" },
  { code: "1-1100", label: "Bank" },
  { code: "1-1110", label: "Bank BCA - Silo" },
  { code: "1-1120", label: "Bank OCBC - Silo" },
];

export default function BiayaPage() {
  const [mode, setMode] = useState<"beban" | "kasbon">("beban");
  const [expenses, setExpenses] = useState<Expense[]>([]);
  const [loans, setLoans] = useState<Loan[]>([]);
  const [accounts, setAccounts] = useState<Account[]>([]);
  const [error, setError] = useState<string | null>(null);

  const [openExp, setOpenExp] = useState(false);
  const [ef, setEf] = useState({ date: today(), category: "umum", description: "", amount: "", expense_account_code: "6-2900", paid_account_code: "1-1000" });

  const [openLoan, setOpenLoan] = useState(false);
  const [lf, setLf] = useState({ employee_name: "", date: today(), amount: "", paid_account_code: "1-1000" });

  const [repay, setRepay] = useState<Loan | null>(null);
  const [rf, setRf] = useState({ date: today(), amount: "", cash_account_code: "1-1000" });

  const [saving, setSaving] = useState(false);
  const [formError, setFormError] = useState<string | null>(null);

  function muat() {
    api<Expense[]>("/expenses").then(setExpenses).catch((e) => setError(e.message));
    api<Loan[]>("/loans").then(setLoans).catch(() => {});
  }
  useEffect(() => {
    muat();
    api<Account[]>("/accounts").then((a) => setAccounts(a.filter((x) => x.type === "expense"))).catch(() => {});
  }, []);

  async function simpanExp(e: FormEvent) {
    e.preventDefault(); setFormError(null);
    if (!(Number(ef.amount) > 0)) return setFormError("Nominal harus lebih dari 0.");
    setSaving(true);
    try {
      await api("/expenses", {
        method: "POST",
        body: JSON.stringify({ ...ef, description: ef.description.trim(), note: null }),
      });
      setOpenExp(false);
      setEf({ date: today(), category: "umum", description: "", amount: "", expense_account_code: "6-2900", paid_account_code: "1-1000" });
      muat();
    } catch (err) { setFormError(err instanceof Error ? err.message : "Gagal menyimpan."); }
    finally { setSaving(false); }
  }

  async function simpanLoan(e: FormEvent) {
    e.preventDefault(); setFormError(null);
    if (!(Number(lf.amount) > 0)) return setFormError("Nominal harus lebih dari 0.");
    setSaving(true);
    try {
      await api("/loans", {
        method: "POST",
        body: JSON.stringify({ ...lf, employee_name: lf.employee_name.trim(), note: null }),
      });
      setOpenLoan(false);
      setLf({ employee_name: "", date: today(), amount: "", paid_account_code: "1-1000" });
      muat();
    } catch (err) { setFormError(err instanceof Error ? err.message : "Gagal menyimpan."); }
    finally { setSaving(false); }
  }

  async function simpanRepay(e: FormEvent) {
    e.preventDefault();
    if (!repay) return;
    setFormError(null);
    if (!(Number(rf.amount) > 0)) return setFormError("Nominal harus lebih dari 0.");
    setSaving(true);
    try {
      await api(`/loans/${repay.id}/repay`, { method: "POST", body: JSON.stringify(rf) });
      setRepay(null);
      muat();
    } catch (err) { setFormError(err instanceof Error ? err.message : "Gagal memproses."); }
    finally { setSaving(false); }
  }

  const sisa = (l: Loan) => Number(l.amount) - Number(l.repaid_total);

  return (
    <>
      <Topbar title="Biaya Operasional" />
      <div className="space-y-4 p-6">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <div className="inline-flex rounded-[var(--radius-button)] border border-line bg-surface-sunken p-1 text-sm">
            <button onClick={() => setMode("beban")}
              className={`rounded-[var(--radius-button)] px-4 py-1.5 font-medium transition-colors ${mode === "beban" ? "bg-surface text-ink shadow-[var(--shadow-pop)]" : "text-ink-muted"}`}>
              Beban / Pengeluaran
            </button>
            <button onClick={() => setMode("kasbon")}
              className={`rounded-[var(--radius-button)] px-4 py-1.5 font-medium transition-colors ${mode === "kasbon" ? "bg-surface text-ink shadow-[var(--shadow-pop)]" : "text-ink-muted"}`}>
              Kasbon Karyawan
            </button>
          </div>
          {mode === "beban"
            ? <Button onClick={() => { setFormError(null); setOpenExp(true); }}><Plus size={16} /> Catat Beban</Button>
            : <Button onClick={() => { setFormError(null); setOpenLoan(true); }}><Plus size={16} /> Kasbon Baru</Button>}
        </div>

        {error && <Card><p className="text-sm text-danger">{error}</p></Card>}

        {mode === "beban" && (
          <Card className="overflow-hidden p-0">
            <table className="w-full text-sm">
              <thead><tr className="border-b border-line text-left text-caption text-ink-muted">
                <th className="px-4 py-3 font-medium">No.</th>
                <th className="px-4 py-3 font-medium">Tanggal</th>
                <th className="px-4 py-3 font-medium">Kategori</th>
                <th className="px-4 py-3 font-medium">Deskripsi</th>
                <th className="px-4 py-3 text-right font-medium">Nominal</th>
              </tr></thead>
              <tbody>
                {expenses.map((x) => (
                  <tr key={x.id} className="border-b border-line last:border-0 hover:bg-surface-sunken">
                    <td className="px-4 py-3 text-ink">{x.number}</td>
                    <td className="px-4 py-3 text-ink-muted">{tanggal(x.date)}</td>
                    <td className="px-4 py-3 capitalize text-ink-muted">{x.category}</td>
                    <td className="px-4 py-3 text-ink">{x.description}</td>
                    <td className="px-4 py-3 text-right tabular-nums text-ink">{rupiah(x.amount)}</td>
                  </tr>
                ))}
                {expenses.length === 0 && <tr><td colSpan={5} className="px-4 py-6 text-center text-ink-subtle">Belum ada beban tercatat. Catat BBM, perawatan armada, listrik, dll — jurnal otomatis.</td></tr>}
              </tbody>
            </table>
          </Card>
        )}

        {mode === "kasbon" && (
          <Card className="overflow-hidden p-0">
            <table className="w-full text-sm">
              <thead><tr className="border-b border-line text-left text-caption text-ink-muted">
                <th className="px-4 py-3 font-medium">No.</th>
                <th className="px-4 py-3 font-medium">Karyawan</th>
                <th className="px-4 py-3 font-medium">Tanggal</th>
                <th className="px-4 py-3 text-right font-medium">Pinjaman</th>
                <th className="px-4 py-3 text-right font-medium">Sisa</th>
                <th className="px-4 py-3 text-right font-medium">Aksi</th>
              </tr></thead>
              <tbody>
                {loans.map((l) => (
                  <tr key={l.id} className="border-b border-line last:border-0 hover:bg-surface-sunken">
                    <td className="px-4 py-3 text-ink">{l.number}</td>
                    <td className="px-4 py-3 text-ink">{l.employee_name}</td>
                    <td className="px-4 py-3 text-ink-muted">{tanggal(l.date)}</td>
                    <td className="px-4 py-3 text-right tabular-nums text-ink">{rupiah(l.amount)}</td>
                    <td className={`px-4 py-3 text-right tabular-nums ${sisa(l) > 0 ? "text-danger" : "text-success"}`}>{rupiah(sisa(l))}</td>
                    <td className="px-4 py-3 text-right">
                      {l.status === "active"
                        ? <Button variant="secondary" onClick={() => { setFormError(null); setRf({ date: today(), amount: String(sisa(l)), cash_account_code: "1-1000" }); setRepay(l); }}>
                            <Wallet size={15} /> Terima Cicilan
                          </Button>
                        : <span className="text-caption text-success">Lunas</span>}
                    </td>
                  </tr>
                ))}
                {loans.length === 0 && <tr><td colSpan={6} className="px-4 py-6 text-center text-ink-subtle">Belum ada kasbon.</td></tr>}
              </tbody>
            </table>
          </Card>
        )}
      </div>

      {/* Modal beban */}
      <Modal open={openExp} onClose={() => setOpenExp(false)} title="Catat Beban">
        <form onSubmit={simpanExp} className="space-y-4">
          <div className="grid grid-cols-2 gap-4">
            <Field label="Tanggal"><input type="date" value={ef.date} onChange={(e) => setEf((f) => ({ ...f, date: e.target.value }))} required className="w-full rounded-[var(--radius-input)] border border-line bg-surface-sunken px-3 py-2 text-sm text-ink focus:border-primary focus:bg-surface focus:outline-none" /></Field>
            <Field label="Kategori">
              <Select value={ef.category} onChange={(e) => setEf((f) => ({ ...f, category: e.target.value }))}>
                <option value="umum">Umum</option>
                <option value="armada">Armada / kendaraan</option>
                <option value="lainnya">Lainnya</option>
              </Select>
            </Field>
          </div>
          <Field label="Deskripsi"><Input value={ef.description} onChange={(e) => setEf((f) => ({ ...f, description: e.target.value }))} required placeholder="BBM mobil box minggu ini" /></Field>
          <div className="grid grid-cols-2 gap-4">
            <Field label="Akun beban">
              <Select value={ef.expense_account_code} onChange={(e) => setEf((f) => ({ ...f, expense_account_code: e.target.value }))}>
                {accounts.map((a) => <option key={a.id} value={a.code}>{a.code} · {a.name}</option>)}
                {accounts.length === 0 && <option value="6-2900">6-2900 · Beban Operasional Lainnya</option>}
              </Select>
            </Field>
            <Field label="Nominal (Rp)"><Input type="number" min={0} value={ef.amount} onChange={(e) => setEf((f) => ({ ...f, amount: e.target.value }))} required /></Field>
          </div>
          <Field label="Dibayar dari">
            <Select value={ef.paid_account_code} onChange={(e) => setEf((f) => ({ ...f, paid_account_code: e.target.value }))}>
              {CASH_OPTS.map((o) => <option key={o.code} value={o.code}>{o.label}</option>)}
            </Select>
          </Field>
          {formError && <p className="text-sm text-danger">{formError}</p>}
          <div className="flex justify-end gap-2 pt-2">
            <Button type="button" variant="secondary" onClick={() => setOpenExp(false)}>Batal</Button>
            <Button type="submit" disabled={saving}>{saving ? "Menyimpan…" : "Simpan"}</Button>
          </div>
        </form>
      </Modal>

      {/* Modal kasbon */}
      <Modal open={openLoan} onClose={() => setOpenLoan(false)} title="Kasbon Baru">
        <form onSubmit={simpanLoan} className="space-y-4">
          <Field label="Nama karyawan"><Input value={lf.employee_name} onChange={(e) => setLf((f) => ({ ...f, employee_name: e.target.value }))} required placeholder="Abay" /></Field>
          <div className="grid grid-cols-2 gap-4">
            <Field label="Tanggal"><input type="date" value={lf.date} onChange={(e) => setLf((f) => ({ ...f, date: e.target.value }))} required className="w-full rounded-[var(--radius-input)] border border-line bg-surface-sunken px-3 py-2 text-sm text-ink focus:border-primary focus:bg-surface focus:outline-none" /></Field>
            <Field label="Nominal (Rp)"><Input type="number" min={0} value={lf.amount} onChange={(e) => setLf((f) => ({ ...f, amount: e.target.value }))} required /></Field>
          </div>
          <Field label="Kas keluar dari">
            <Select value={lf.paid_account_code} onChange={(e) => setLf((f) => ({ ...f, paid_account_code: e.target.value }))}>
              {CASH_OPTS.map((o) => <option key={o.code} value={o.code}>{o.label}</option>)}
            </Select>
          </Field>
          <p className="text-caption text-ink-subtle">Kasbon dicatat sebagai Piutang Karyawan (1-1600) — pastikan seed_extras sudah dijalankan.</p>
          {formError && <p className="text-sm text-danger">{formError}</p>}
          <div className="flex justify-end gap-2 pt-2">
            <Button type="button" variant="secondary" onClick={() => setOpenLoan(false)}>Batal</Button>
            <Button type="submit" disabled={saving}>{saving ? "Menyimpan…" : "Simpan"}</Button>
          </div>
        </form>
      </Modal>

      {/* Modal cicilan */}
      <Modal open={!!repay} onClose={() => setRepay(null)} title={`Terima Cicilan — ${repay?.employee_name ?? ""}`}>
        <form onSubmit={simpanRepay} className="space-y-4">
          <div className="grid grid-cols-2 gap-4">
            <Field label="Tanggal"><input type="date" value={rf.date} onChange={(e) => setRf((f) => ({ ...f, date: e.target.value }))} required className="w-full rounded-[var(--radius-input)] border border-line bg-surface-sunken px-3 py-2 text-sm text-ink focus:border-primary focus:bg-surface focus:outline-none" /></Field>
            <Field label="Nominal (Rp)"><Input type="number" min={0} value={rf.amount} onChange={(e) => setRf((f) => ({ ...f, amount: e.target.value }))} required /></Field>
          </div>
          <Field label="Kas masuk ke">
            <Select value={rf.cash_account_code} onChange={(e) => setRf((f) => ({ ...f, cash_account_code: e.target.value }))}>
              {CASH_OPTS.map((o) => <option key={o.code} value={o.code}>{o.label}</option>)}
            </Select>
          </Field>
          {formError && <p className="text-sm text-danger">{formError}</p>}
          <div className="flex justify-end gap-2 pt-2">
            <Button type="button" variant="secondary" onClick={() => setRepay(null)}>Batal</Button>
            <Button type="submit" disabled={saving}>{saving ? "Memproses…" : "Catat Cicilan"}</Button>
          </div>
        </form>
      </Modal>
    </>
  );
}

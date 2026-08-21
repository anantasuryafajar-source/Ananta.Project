"use client";
import { useEffect, useState } from "react";
import { Lock } from "lucide-react";
import { api } from "@/lib/api";
import { rupiah, tanggal } from "@/lib/format";
import { Topbar } from "@/components/ananta/topbar";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";

type KomisiBaris = {
  line_id: string; sheet_number: string; invoice_number: string;
  invoice_status: string; payee_name: string; jenis: string;
  amount: string; sisa_piutang: string;
};
type Hak = {
  id: string; number: string; date: string; jenis: string;
  payee_name: string; periode: string; amount: string;
};
type Data = {
  komisi_siap_transfer: KomisiBaris[];
  komisi_tertahan: KomisiBaris[];
  total_siap: string; total_tertahan: string;
  hak_internal: Hak[]; total_hak_internal: string;
};

const today = () => new Date().toISOString().slice(0, 10);
const LABEL_JENIS: Record<string, string> = {
  komisi: "Komisi pihak luar", bagi_hasil: "Hak mitra",
  insentif: "Insentif penjualan", omzet: "Bagi hasil omzet",
};

export default function DisbursementPage() {
  const [data, setData] = useState<Data | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [sibuk, setSibuk] = useState<string | null>(null);

  function muat() {
    api<Data>("/payouts/disbursement").then(setData).catch((e) => setError(e.message));
  }
  useEffect(muat, []);

  async function transferKomisi(b: KomisiBaris) {
    setSibuk(b.line_id); setError(null);
    try {
      await api(`/profit-sheets/lines/${b.line_id}/transfer`, {
        method: "POST",
        body: JSON.stringify({ date: today(), paid_account_code: "1-1000" }),
      });
      muat();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Gagal transfer.");
    } finally { setSibuk(null); }
  }

  async function bayarHak(h: Hak) {
    setSibuk(h.id); setError(null);
    try {
      await api(`/payouts/${h.id}/pay`, {
        method: "POST",
        body: JSON.stringify({ date: today(), paid_account_code: "1-1000" }),
      });
      muat();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Gagal membayar.");
    } finally { setSibuk(null); }
  }

  return (
    <>
      <Topbar title="Disbursement" />
      <div className="p-6">
        <Card className="mb-4">
          <p className="text-sm text-ink">
            Transfer fisik komisi pihak luar hanya dibuka untuk faktur yang sudah{" "}
            <b>lunas</b>.
          </p>
          <p className="mt-1 text-caption text-ink-subtle">
            Haknya sendiri sudah diakui sebagai beban sejak lembar hitung disetujui —
            membayar di sini cuma menutup utang, tidak menggerakkan Laba Rugi.
          </p>
        </Card>

        {error && <Card className="mb-4"><p className="text-sm text-danger">{error}</p></Card>}

        {/* ---- Komisi siap transfer ---- */}
        <div className="mb-2 flex items-baseline justify-between">
          <h2 className="text-ink">Komisi pihak luar — siap transfer</h2>
          <span className="tabular-nums text-sm text-ink">
            {rupiah(data?.total_siap ?? 0)}
          </span>
        </div>
        <Card className="mb-6 overflow-hidden p-0">
          {data?.komisi_siap_transfer.length ? (
            <table className="w-full text-sm">
              <thead><tr className="border-b border-line text-left text-caption text-ink-muted">
                <th className="px-4 py-3 font-medium">Penerima</th>
                <th className="px-4 py-3 font-medium">Faktur</th>
                <th className="px-4 py-3 font-medium">Jenis</th>
                <th className="px-4 py-3 text-right font-medium">Nilai</th>
                <th className="px-4 py-3" />
              </tr></thead>
              <tbody>
                {data.komisi_siap_transfer.map((b) => (
                  <tr key={b.line_id} className="border-b border-line last:border-0">
                    <td className="px-4 py-3 text-ink">{b.payee_name}</td>
                    <td className="px-4 py-3 text-ink-muted">{b.invoice_number}</td>
                    <td className="px-4 py-3 text-ink-muted">
                      {LABEL_JENIS[b.jenis] ?? b.jenis}
                    </td>
                    <td className="px-4 py-3 text-right tabular-nums text-ink">
                      {rupiah(b.amount)}
                    </td>
                    <td className="px-4 py-3 text-right">
                      <Button variant="secondary" disabled={sibuk === b.line_id}
                        onClick={() => transferKomisi(b)}>
                        {sibuk === b.line_id ? "…" : "Transfer"}
                      </Button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          ) : (
            <p className="px-4 py-6 text-center text-sm text-ink-muted">
              Tidak ada komisi yang siap ditransfer.
            </p>
          )}
        </Card>

        {/* ---- Tertahan ---- */}
        {data && data.komisi_tertahan.length > 0 && (
          <>
            <div className="mb-2 flex items-baseline justify-between">
              <h2 className="flex items-center gap-2 text-ink">
                <Lock size={14} className="text-ink-subtle" />
                Tertahan — faktur belum lunas
              </h2>
              <span className="tabular-nums text-sm text-ink-muted">
                {rupiah(data.total_tertahan)}
              </span>
            </div>
            <Card className="mb-6 overflow-hidden p-0">
              <table className="w-full text-sm">
                <thead><tr className="border-b border-line text-left text-caption text-ink-muted">
                  <th className="px-4 py-3 font-medium">Penerima</th>
                  <th className="px-4 py-3 font-medium">Faktur</th>
                  <th className="px-4 py-3 text-right font-medium">Sisa piutang</th>
                  <th className="px-4 py-3 text-right font-medium">Nilai</th>
                </tr></thead>
                <tbody>
                  {data.komisi_tertahan.map((b) => (
                    <tr key={b.line_id} className="border-b border-line last:border-0">
                      <td className="px-4 py-3 text-ink">{b.payee_name}</td>
                      <td className="px-4 py-3 text-ink-muted">{b.invoice_number}</td>
                      <td className="px-4 py-3 text-right tabular-nums text-ink-muted">
                        {rupiah(b.sisa_piutang)}
                      </td>
                      <td className="px-4 py-3 text-right tabular-nums text-ink-muted">
                        {rupiah(b.amount)}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </Card>
            <p className="-mt-4 mb-6 text-caption text-ink-subtle">
              Angka tertahan sengaja tidak dijumlah dengan yang siap transfer —
              gabungannya akan selalu tampak lebih besar dari kas yang boleh keluar.
            </p>
          </>
        )}

        {/* ---- Hak internal ---- */}
        <div className="mb-2 flex items-baseline justify-between">
          <h2 className="text-ink">Hak internal — insentif &amp; bagi hasil omzet</h2>
          <span className="tabular-nums text-sm text-ink">
            {rupiah(data?.total_hak_internal ?? 0)}
          </span>
        </div>
        <Card className="overflow-hidden p-0">
          {data?.hak_internal.length ? (
            <table className="w-full text-sm">
              <thead><tr className="border-b border-line text-left text-caption text-ink-muted">
                <th className="px-4 py-3 font-medium">No.</th>
                <th className="px-4 py-3 font-medium">Penerima</th>
                <th className="px-4 py-3 font-medium">Jenis</th>
                <th className="px-4 py-3 font-medium">Periode</th>
                <th className="px-4 py-3 text-right font-medium">Nilai</th>
                <th className="px-4 py-3" />
              </tr></thead>
              <tbody>
                {data.hak_internal.map((h) => (
                  <tr key={h.id} className="border-b border-line last:border-0">
                    <td className="px-4 py-3 text-ink-muted">{h.number}</td>
                    <td className="px-4 py-3 text-ink">{h.payee_name}</td>
                    <td className="px-4 py-3 text-ink-muted">
                      {LABEL_JENIS[h.jenis] ?? h.jenis}
                    </td>
                    <td className="px-4 py-3 text-ink-muted">{h.periode}</td>
                    <td className="px-4 py-3 text-right tabular-nums text-ink">
                      {rupiah(h.amount)}
                    </td>
                    <td className="px-4 py-3 text-right">
                      <Button variant="secondary" disabled={sibuk === h.id}
                        onClick={() => bayarHak(h)}>
                        {sibuk === h.id ? "…" : "Bayar"}
                      </Button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          ) : (
            <p className="px-4 py-6 text-center text-sm text-ink-muted">
              Belum ada hak internal yang terutang.
            </p>
          )}
        </Card>
      </div>
    </>
  );
}

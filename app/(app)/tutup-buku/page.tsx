"use client";
import { useEffect, useState } from "react";
import { AlertTriangle, Check, X } from "lucide-react";
import { api } from "@/lib/api";
import { rupiah } from "@/lib/format";
import { Topbar } from "@/components/ananta/topbar";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Field, Select } from "@/components/ui/form";

type Laporan = {
  periode: string;
  target: {
    tercapai: boolean; omzet: string; uang_masuk_bersih: string;
    ambang: string; kurang_omzet: string; kurang_uang_masuk: string;
  };
  laba_kotor: string | null;
  komisi_pihak_luar: { siap_transfer: string; tertahan_belum_lunas: string };
  bonus_internal: {
    basis_term1: string; basis_term2: string; sudah_cair_tgl16: string;
    bonus_term2: string; booster_term1: string; cair_tgl1: string; hangus: string;
  };
  dividen: { nyokap_sam: string; delvina: string; total: string; hangus: string };
  disbursement_tgl1: {
    bonus_internal: string; dividen: string; komisi_pihak_luar: string; total: string;
  };
  peringatan: string[];
  mode?: string;
  dijurnalkan?: string[];
};

const BULAN = ["Januari", "Februari", "Maret", "April", "Mei", "Juni", "Juli",
  "Agustus", "September", "Oktober", "November", "Desember"];

function Baris({ label, nilai, tebal = false, redup = false }: {
  label: string; nilai: string; tebal?: boolean; redup?: boolean;
}) {
  return (
    <div className="flex justify-between py-1 text-sm">
      <span className={redup ? "text-ink-subtle" : "text-ink-muted"}>{label}</span>
      <span className={`tabular-nums ${tebal ? "font-medium text-ink" : redup ? "text-ink-subtle" : "text-ink"}`}>
        {nilai}
      </span>
    </div>
  );
}

export default function TutupBukuPage() {
  const kini = new Date();
  const [tahun, setTahun] = useState(String(kini.getFullYear()));
  const [bulan, setBulan] = useState(String(kini.getMonth() + 1));
  const [laporan, setLaporan] = useState<Laporan | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [muat, setMuatState] = useState(false);
  const [eksekusi, setEksekusi] = useState(false);
  const [konfirmasi, setKonfirmasi] = useState(false);

  async function pratinjau() {
    setMuatState(true); setError(null); setKonfirmasi(false);
    try {
      setLaporan(await api<Laporan>(
        `/payouts/tutup-buku/pratinjau?tahun=${tahun}&bulan=${bulan}`));
    } catch (e) {
      setLaporan(null);
      setError(e instanceof Error ? e.message : "Gagal memuat.");
    } finally { setMuatState(false); }
  }
  useEffect(() => { pratinjau(); }, []);   // eslint-disable-line react-hooks/exhaustive-deps

  async function terapkan() {
    setEksekusi(true); setError(null);
    try {
      setLaporan(await api<Laporan>("/payouts/tutup-buku", {
        method: "POST",
        body: JSON.stringify({ tahun: Number(tahun), bulan: Number(bulan),
                               terapkan: true }),
      }));
      setKonfirmasi(false);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Gagal menjurnalkan.");
    } finally { setEksekusi(false); }
  }

  const t = laporan?.target;

  return (
    <>
      <Topbar title="Tutup Buku Bulanan" />
      <div className="p-6">
        <Card className="mb-4">
          <div className="flex flex-wrap items-end gap-3">
            <Field label="Bulan">
              <Select value={bulan} onChange={(e) => setBulan(e.target.value)}>
                {BULAN.map((b, i) => <option key={b} value={i + 1}>{b}</option>)}
              </Select>
            </Field>
            <Field label="Tahun">
              <Select value={tahun} onChange={(e) => setTahun(e.target.value)}>
                {[kini.getFullYear() - 1, kini.getFullYear()].map((y) => (
                  <option key={y} value={y}>{y}</option>
                ))}
              </Select>
            </Field>
            <Button variant="secondary" onClick={pratinjau} disabled={muat}>
              {muat ? "Memuat…" : "Pratinjau"}
            </Button>
          </div>
          <p className="mt-3 text-caption text-ink-subtle">
            Pratinjau tidak menyentuh jurnal sama sekali. Angkanya disusun dari
            transaksi bulan itu, bukan diketik ulang.
          </p>
        </Card>

        {error && <Card className="mb-4"><p className="text-sm text-danger">{error}</p></Card>}

        {laporan && t && (
          <>
            {/* ---- Gerbang target ---- */}
            <Card className="mb-4">
              <div className="flex items-center gap-2">
                {t.tercapai
                  ? <Check size={18} className="text-success" />
                  : <X size={18} className="text-danger" />}
                <span className="font-medium text-ink">
                  Target bulanan {t.tercapai ? "TERCAPAI" : "TIDAK tercapai"}
                </span>
              </div>
              <div className="mt-2">
                <Baris label={`Omzet (ambang ${rupiah(t.ambang)})`} nilai={rupiah(t.omzet)} />
                <Baris label={`Uang masuk bersih (ambang ${rupiah(t.ambang)})`}
                  nilai={rupiah(t.uang_masuk_bersih)} />
                {laporan.laba_kotor && (
                  <Baris label="Laba kotor bulan ini" nilai={rupiah(laporan.laba_kotor)} redup />
                )}
              </div>
              {!t.tercapai && (
                <p className="mt-2 text-caption text-ink-subtle">
                  Butuh dua syarat sekaligus. Kurang{" "}
                  {Number(t.kurang_omzet) > 0 && `omzet ${rupiah(t.kurang_omzet)}`}
                  {Number(t.kurang_omzet) > 0 && Number(t.kurang_uang_masuk) > 0 && " dan "}
                  {Number(t.kurang_uang_masuk) > 0 && `uang masuk ${rupiah(t.kurang_uang_masuk)}`}.
                </p>
              )}
            </Card>

            {laporan.peringatan.map((p, i) => (
              <Card key={i} className="mb-4 border-warning">
                <p className="flex gap-2 text-sm text-ink">
                  <AlertTriangle size={16} className="mt-0.5 shrink-0 text-warning" />
                  {p}
                </p>
              </Card>
            ))}

            <div className="grid gap-4 md:grid-cols-2">
              <Card>
                <h2 className="mb-2 text-ink">Bonus internal</h2>
                <Baris label="Dasar Term 1 (tgl 1–15)" nilai={rupiah(laporan.bonus_internal.basis_term1)} redup />
                <Baris label="Dasar Term 2 (tgl 16–akhir)" nilai={rupiah(laporan.bonus_internal.basis_term2)} redup />
                <div className="my-1 border-t border-line" />
                <Baris label="Sudah cair tgl 16 (4,3%)" nilai={rupiah(laporan.bonus_internal.sudah_cair_tgl16)} />
                <Baris label="Bonus Term 2 (5,3%)" nilai={rupiah(laporan.bonus_internal.bonus_term2)} />
                <Baris label="Booster Term 1 (1,0%)" nilai={rupiah(laporan.bonus_internal.booster_term1)} />
                <Baris label="Cair tanggal 1" nilai={rupiah(laporan.bonus_internal.cair_tgl1)} tebal />
                {Number(laporan.bonus_internal.hangus) > 0 && (
                  <Baris label="Hangus (target meleset)" nilai={rupiah(laporan.bonus_internal.hangus)} redup />
                )}
              </Card>

              <Card>
                <h2 className="mb-2 text-ink">Bagi hasil omzet</h2>
                <Baris label="Nyokap Sam (18%)" nilai={rupiah(laporan.dividen.nyokap_sam)} />
                <Baris label="Delvina (14%)" nilai={rupiah(laporan.dividen.delvina)} />
                <Baris label="Total" nilai={rupiah(laporan.dividen.total)} tebal />
                {Number(laporan.dividen.hangus) > 0 && (
                  <Baris label="Hangus (target meleset)" nilai={rupiah(laporan.dividen.hangus)} redup />
                )}
              </Card>

              <Card>
                <h2 className="mb-2 text-ink">Komisi pihak luar</h2>
                <Baris label="Siap transfer (faktur lunas)" nilai={rupiah(laporan.komisi_pihak_luar.siap_transfer)} />
                <Baris label="Tertahan (belum lunas)" nilai={rupiah(laporan.komisi_pihak_luar.tertahan_belum_lunas)} redup />
              </Card>

              <Card>
                <h2 className="mb-2 text-ink">Total transfer tanggal 1</h2>
                <Baris label="Bonus internal" nilai={rupiah(laporan.disbursement_tgl1.bonus_internal)} />
                <Baris label="Bagi hasil omzet" nilai={rupiah(laporan.disbursement_tgl1.dividen)} />
                <Baris label="Komisi pihak luar" nilai={rupiah(laporan.disbursement_tgl1.komisi_pihak_luar)} />
                <div className="my-1 border-t border-line" />
                <Baris label="TOTAL" nilai={rupiah(laporan.disbursement_tgl1.total)} tebal />
              </Card>
            </div>

            {/* ---- Eksekusi ---- */}
            <Card className="mt-4">
              {laporan.dijurnalkan && laporan.dijurnalkan.length > 0 ? (
                <p className="text-sm text-ink">
                  Sudah dijurnalkan: {laporan.dijurnalkan.join(", ")}.
                </p>
              ) : laporan.mode === "terapkan" ? (
                <p className="text-sm text-ink-muted">
                  Tidak ada yang baru dijurnalkan — periode ini sudah diakrual
                  sebelumnya, atau target tidak tercapai.
                </p>
              ) : !konfirmasi ? (
                <div className="flex items-center justify-between">
                  <p className="text-sm text-ink-muted">
                    Menerapkan akan membuat jurnal beban &amp; utang untuk hak yang
                    lolos gerbang. Aman diulang.
                  </p>
                  <Button onClick={() => setKonfirmasi(true)} disabled={!t.tercapai}>
                    Terapkan Jurnal
                  </Button>
                </div>
              ) : (
                <div className="flex items-center justify-between">
                  <p className="text-sm text-ink">
                    Jurnalkan{" "}
                    <b>{rupiah(Number(laporan.disbursement_tgl1.bonus_internal)
                      + Number(laporan.disbursement_tgl1.dividen))}</b>{" "}
                    sebagai beban &amp; utang untuk {laporan.periode}?
                  </p>
                  <div className="flex gap-2">
                    <Button variant="secondary" onClick={() => setKonfirmasi(false)}>
                      Batal
                    </Button>
                    <Button onClick={terapkan} disabled={eksekusi}>
                      {eksekusi ? "Memproses…" : "Ya, jurnalkan"}
                    </Button>
                  </div>
                </div>
              )}
              {!t.tercapai && laporan.mode !== "terapkan" && (
                <p className="mt-2 text-caption text-ink-subtle">
                  Target belum tercapai — tidak ada bonus Term 2 maupun bagi hasil
                  omzet yang bisa diakui. Bonus Term 1 yang sudah cair tanggal 16
                  tidak ditarik kembali.
                </p>
              )}
            </Card>
          </>
        )}
      </div>
    </>
  );
}

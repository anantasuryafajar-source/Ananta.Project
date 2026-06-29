"use client";
import { Topbar } from "@/components/ananta/topbar";
import { Card } from "@/components/ui/card";

export default function Page() {
  return (
    <>
      <Topbar title="Pengaturan" />
      <div className="p-6">
        <Card className="text-center">
          <p className="text-ink">Modul Pengaturan</p>
          <p className="mt-1 text-sm text-ink-muted">Perusahaan, peran, dan gudang dikonfigurasi via seed_asf & API.</p>
        </Card>
      </div>
    </>
  );
}

"use client";
import { Topbar } from "@/components/ananta/topbar";
import { Card } from "@/components/ui/card";

export default function Page() {
  return (
    <>
      <Topbar title="Kas & Bank" />
      <div className="p-6">
        <Card className="text-center">
          <p className="text-ink">Modul Kas & Bank</p>
          <p className="mt-1 text-sm text-ink-muted">Akun 1-1000 / 1-1100 + POST /api/v1/payments untuk pelunasan.</p>
        </Card>
      </div>
    </>
  );
}

"use client";

import { useEffect, useRef, useState } from "react";
import { Sparkles, ArrowUp } from "lucide-react";
import { api } from "@/lib/api";

/**
 * Halaman Asisten AI (UX untuk anantaasf.com).
 *
 * Kontrak backend (diimplementasikan developer AI, TERPISAH dari bot Telegram):
 *   POST /api/v1/ai/chat
 *   body : { messages: { role: "user" | "assistant"; content: string }[] }
 *   resp : { reply: string }
 *
 * Halaman ini murni UX + memanggil endpoint di atas. Selama endpoint belum ada,
 * pesan akan menampilkan galat yang ramah (bukan crash).
 */

type Msg = { role: "user" | "assistant"; content: string };

const CONTOH = [
  "Bagaimana laba rugi bulan ini?",
  "Siapa customer dengan piutang terbesar?",
  "Berapa nilai persediaan saat ini?",
];

export default function AsistenPage() {
  const [messages, setMessages] = useState<Msg[]>([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const scrollRef = useRef<HTMLDivElement>(null);
  const taRef = useRef<HTMLTextAreaElement>(null);

  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: "smooth" });
  }, [messages, loading]);

  function grow() {
    const el = taRef.current;
    if (!el) return;
    el.style.height = "auto";
    el.style.height = Math.min(el.scrollHeight, 200) + "px";
  }

  async function send(text: string) {
    const q = text.trim();
    if (!q || loading) return;
    const next = [...messages, { role: "user", content: q } as Msg];
    setMessages(next);
    setInput("");
    if (taRef.current) taRef.current.style.height = "auto";
    setLoading(true);
    try {
      const res = await api<{ reply: string }>("/ai/chat", {
        method: "POST",
        body: JSON.stringify({ messages: next }),
      });
      setMessages([...next, { role: "assistant", content: res?.reply ?? "(kosong)" }]);
    } catch (e) {
      const msg = e instanceof Error ? e.message : "Terjadi kesalahan.";
      setMessages([
        ...next,
        { role: "assistant", content: `Belum bisa menjawab: ${msg}` },
      ]);
    } finally {
      setLoading(false);
    }
  }

  function onKey(e: React.KeyboardEvent<HTMLTextAreaElement>) {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      send(input);
    }
  }

  const empty = messages.length === 0;

  return (
    <div className="flex h-screen flex-col bg-[var(--canvas)]">
      {/* Header */}
      <header className="flex items-center gap-3 border-b border-line bg-surface px-6 py-4">
        <span className="grid h-9 w-9 place-items-center rounded-[var(--radius-input)] bg-[var(--primary-soft)] text-primary">
          <Sparkles size={18} />
        </span>
        <div>
          <h1 className="font-display text-lg font-bold leading-none text-ink">Asisten AI</h1>
          <p className="mt-1 text-caption text-ink-subtle">
            Analisis keuangan bisnismu, berbasis data Ananta
          </p>
        </div>
      </header>

      {/* Thread */}
      <div ref={scrollRef} className="flex-1 overflow-y-auto">
        <div className="mx-auto w-full max-w-3xl px-4 py-6">
          {empty ? (
            <div className="mt-10 flex flex-col items-center text-center">
              <span className="grid h-14 w-14 place-items-center rounded-full bg-[var(--primary-soft)] text-primary">
                <Sparkles size={26} />
              </span>
              <h2 className="mt-4 font-display text-xl font-bold text-ink">
                Ada yang bisa dibantu?
              </h2>
              <p className="mt-1 max-w-md text-sm text-ink-muted">
                Tanyakan apa saja tentang keuangan bisnismu. Asisten membaca data riil
                (laba rugi, piutang, stok) untuk menjawab.
              </p>
              <div className="mt-6 flex w-full max-w-md flex-col gap-2">
                {CONTOH.map((c) => (
                  <button
                    key={c}
                    onClick={() => send(c)}
                    className="rounded-[var(--radius-input)] border border-line bg-surface px-4 py-3 text-left text-sm text-ink transition-colors hover:border-primary hover:bg-surface-sunken"
                  >
                    {c}
                  </button>
                ))}
              </div>
            </div>
          ) : (
            <div className="flex flex-col gap-5">
              {messages.map((m, i) => (
                <Bubble key={i} msg={m} />
              ))}
              {loading && <Thinking />}
            </div>
          )}
        </div>
      </div>

      {/* Composer */}
      <div className="border-t border-line bg-surface px-4 py-3">
        <div className="mx-auto w-full max-w-3xl">
          <div className="flex items-end gap-2 rounded-[var(--radius-button)] border border-line bg-surface-sunken px-3 py-2 focus-within:border-primary focus-within:bg-surface">
            <textarea
              ref={taRef}
              rows={1}
              value={input}
              onChange={(e) => {
                setInput(e.target.value);
                grow();
              }}
              onKeyDown={onKey}
              placeholder="Tulis pertanyaan…"
              className="max-h-[200px] flex-1 resize-none bg-transparent py-1.5 text-sm text-ink outline-none placeholder:text-ink-subtle"
            />
            <button
              onClick={() => send(input)}
              disabled={!input.trim() || loading}
              aria-label="Kirim"
              className="grid h-8 w-8 shrink-0 place-items-center rounded-full bg-primary text-white transition-colors hover:bg-[var(--primary-hover)] disabled:opacity-40"
            >
              <ArrowUp size={16} />
            </button>
          </div>
          <p className="mt-2 text-center text-caption text-ink-subtle">
            Asisten bisa keliru. Verifikasi angka penting di menu Laporan.
          </p>
        </div>
      </div>
    </div>
  );
}

function Bubble({ msg }: { msg: Msg }) {
  const isUser = msg.role === "user";
  if (isUser) {
    return (
      <div className="flex justify-end">
        <div className="max-w-[85%] whitespace-pre-wrap rounded-[var(--radius-button)] bg-[var(--primary-soft)] px-4 py-2.5 text-sm text-ink">
          {msg.content}
        </div>
      </div>
    );
  }
  return (
    <div className="flex gap-3">
      <span className="mt-0.5 grid h-7 w-7 shrink-0 place-items-center rounded-full bg-[var(--primary-soft)] text-primary">
        <Sparkles size={15} />
      </span>
      <div className="whitespace-pre-wrap pt-0.5 text-sm leading-relaxed text-ink">
        {msg.content}
      </div>
    </div>
  );
}

function Thinking() {
  return (
    <div className="flex gap-3">
      <span className="mt-0.5 grid h-7 w-7 shrink-0 place-items-center rounded-full bg-[var(--primary-soft)] text-primary">
        <Sparkles size={15} />
      </span>
      <div className="flex items-center gap-1.5 pt-2">
        <Dot delay="0ms" />
        <Dot delay="150ms" />
        <Dot delay="300ms" />
      </div>
    </div>
  );
}

function Dot({ delay }: { delay: string }) {
  return (
    <span
      className="h-1.5 w-1.5 animate-pulse rounded-full bg-[var(--ink-subtle)]"
      style={{ animationDelay: delay }}
    />
  );
}

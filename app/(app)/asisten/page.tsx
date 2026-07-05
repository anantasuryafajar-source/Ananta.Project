"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { Sparkles, ArrowUp, Plus, Trash2, PanelLeft } from "lucide-react";
import { api } from "@/lib/api";

/**
 * Asisten AI (web anantaasf.com) — riwayat tersimpan + pilihan model & effort.
 * Backend: /api/v1/ai/*  (terpisah dari bot Telegram).
 */

type Msg = { role: "user" | "assistant"; content: string };
type Conv = { id: string; title: string };
type Opt = { id: string; label: string };

const CONTOH = [
  "Bagaimana laba rugi bulan ini?",
  "Siapa customer dengan piutang terbesar?",
  "Berapa nilai persediaan saat ini?",
];

export default function AsistenPage() {
  const [convs, setConvs] = useState<Conv[]>([]);
  const [activeId, setActiveId] = useState<string | null>(null);
  const [messages, setMessages] = useState<Msg[]>([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [panel, setPanel] = useState(true);

  const [models, setModels] = useState<Opt[]>([]);
  const [efforts, setEfforts] = useState<Opt[]>([]);
  const [model, setModel] = useState("");
  const [effort, setEffort] = useState("");

  const scrollRef = useRef<HTMLDivElement>(null);
  const taRef = useRef<HTMLTextAreaElement>(null);

  const loadConvs = useCallback(async () => {
    try {
      setConvs(await api<Conv[]>("/ai/conversations"));
    } catch {
      /* endpoint belum ada -> biarkan kosong */
    }
  }, []);

  useEffect(() => {
    (async () => {
      try {
        const cfg = await api<{
          models: Opt[];
          default_model: string;
          efforts: Opt[];
          default_effort: string;
        }>("/ai/config");
        setModels(cfg.models);
        setEfforts(cfg.efforts);
        setModel(cfg.default_model);
        setEffort(cfg.default_effort);
      } catch {
        /* fallback statis bila backend belum ada */
        setModels([{ id: "claude-sonnet-5", label: "Sonnet (seimbang)" }]);
        setEfforts([
          { id: "low", label: "Rendah" },
          { id: "medium", label: "Sedang" },
          { id: "high", label: "Tinggi" },
        ]);
        setModel("claude-sonnet-5");
        setEffort("medium");
      }
    })();
    loadConvs();
  }, [loadConvs]);

  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: "smooth" });
  }, [messages, loading]);

  function grow() {
    const el = taRef.current;
    if (!el) return;
    el.style.height = "auto";
    el.style.height = Math.min(el.scrollHeight, 200) + "px";
  }

  async function openConv(id: string) {
    setActiveId(id);
    setMessages([]);
    try {
      setMessages(await api<Msg[]>(`/ai/conversations/${id}/messages`));
    } catch {
      /* ignore */
    }
  }

  function newChat() {
    setActiveId(null);
    setMessages([]);
    setInput("");
  }

  async function removeConv(id: string, e: React.MouseEvent) {
    e.stopPropagation();
    try {
      await api(`/ai/conversations/${id}`, { method: "DELETE" });
    } catch {
      /* ignore */
    }
    if (activeId === id) newChat();
    loadConvs();
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
      const res = await api<{ conversation_id: string; title: string; reply: string }>(
        "/ai/chat",
        {
          method: "POST",
          body: JSON.stringify({
            conversation_id: activeId,
            message: q,
            model,
            effort,
          }),
        },
      );
      setMessages([...next, { role: "assistant", content: res.reply }]);
      if (!activeId) {
        setActiveId(res.conversation_id);
        loadConvs();
      }
    } catch (e) {
      const msg = e instanceof Error ? e.message : "Terjadi kesalahan.";
      setMessages([...next, { role: "assistant", content: `Belum bisa menjawab: ${msg}` }]);
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
    <div className="flex h-screen bg-[var(--canvas)]">
      {/* Panel riwayat */}
      {panel && (
        <aside className="hidden w-64 shrink-0 flex-col border-r border-line bg-surface md:flex">
          <div className="p-3">
            <button
              onClick={newChat}
              className="flex w-full items-center justify-center gap-2 rounded-[var(--radius-button)] bg-primary px-3 py-2 text-sm font-medium text-white transition-colors hover:bg-[var(--primary-hover)]"
            >
              <Plus size={16} /> Chat baru
            </button>
          </div>
          <div className="flex-1 space-y-0.5 overflow-y-auto px-2 pb-3">
            {convs.length === 0 && (
              <p className="px-2 py-4 text-caption text-ink-subtle">Belum ada percakapan.</p>
            )}
            {convs.map((c) => (
              <div
                key={c.id}
                onClick={() => openConv(c.id)}
                className={`group flex cursor-pointer items-center gap-2 rounded-[var(--radius-input)] px-3 py-2 text-sm ${
                  activeId === c.id
                    ? "bg-[var(--primary-soft)] text-ink"
                    : "text-ink-muted hover:bg-surface-sunken"
                }`}
              >
                <span className="flex-1 truncate">{c.title}</span>
                <button
                  onClick={(e) => removeConv(c.id, e)}
                  aria-label="Hapus"
                  className="shrink-0 text-ink-subtle opacity-0 transition-opacity hover:text-danger group-hover:opacity-100"
                >
                  <Trash2 size={14} />
                </button>
              </div>
            ))}
          </div>
        </aside>
      )}

      {/* Area chat */}
      <div className="flex flex-1 flex-col">
        {/* Header */}
        <header className="flex items-center gap-3 border-b border-line bg-surface px-4 py-3">
          <button
            onClick={() => setPanel((p) => !p)}
            aria-label="Riwayat"
            className="hidden rounded-[var(--radius-input)] p-1.5 text-ink-muted hover:bg-surface-sunken md:block"
          >
            <PanelLeft size={18} />
          </button>
          <span className="grid h-9 w-9 place-items-center rounded-[var(--radius-input)] bg-[var(--primary-soft)] text-primary">
            <Sparkles size={18} />
          </span>
          <div className="flex-1">
            <h1 className="font-display text-base font-bold leading-none text-ink">Asisten AI</h1>
            <p className="mt-0.5 text-caption text-ink-subtle">Berbasis data Ananta</p>
          </div>
          {/* Dropdown model & effort */}
          <div className="flex items-center gap-2">
            <Select value={model} onChange={setModel} options={models} />
            <Select value={effort} onChange={setEffort} options={efforts} />
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
                <h2 className="mt-4 font-display text-xl font-bold text-ink">Ada yang bisa dibantu?</h2>
                <p className="mt-1 max-w-md text-sm text-ink-muted">
                  Tanyakan apa saja tentang keuangan bisnismu. Asisten membaca data riil untuk menjawab.
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
    </div>
  );
}

function Select({
  value,
  onChange,
  options,
}: {
  value: string;
  onChange: (v: string) => void;
  options: Opt[];
}) {
  return (
    <select
      value={value}
      onChange={(e) => onChange(e.target.value)}
      className="rounded-[var(--radius-input)] border border-line bg-surface px-2 py-1.5 text-caption text-ink outline-none focus:border-primary"
    >
      {options.map((o) => (
        <option key={o.id} value={o.id}>
          {o.label}
        </option>
      ))}
    </select>
  );
}

function Bubble({ msg }: { msg: Msg }) {
  if (msg.role === "user") {
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
      <div className="whitespace-pre-wrap pt-0.5 text-sm leading-relaxed text-ink">{msg.content}</div>
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
        {["0ms", "150ms", "300ms"].map((d) => (
          <span
            key={d}
            className="h-1.5 w-1.5 animate-pulse rounded-full bg-[var(--ink-subtle)]"
            style={{ animationDelay: d }}
          />
        ))}
      </div>
    </div>
  );
}

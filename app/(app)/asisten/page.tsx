"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import {
  Sparkles, ArrowUp, Plus, Trash2, PanelLeft, ChevronDown, Paperclip, X,
} from "lucide-react";
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
  "Bandingkan omzet lempar vs collect.",
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
      /* endpoint belum ada -> kosong */
    }
  }, []);

  useEffect(() => {
    (async () => {
      try {
        const cfg = await api<{
          models: Opt[]; default_model: string; efforts: Opt[]; default_effort: string;
        }>("/ai/config");
        setModels(cfg.models);
        setEfforts(cfg.efforts);
        setModel(cfg.default_model);
        setEffort(cfg.default_effort);
      } catch {
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
    } catch { /* ignore */ }
  }

  function newChat() {
    setActiveId(null);
    setMessages([]);
    setInput("");
    taRef.current?.focus();
  }

  async function removeConv(id: string, e: React.MouseEvent) {
    e.stopPropagation();
    try {
      await api(`/ai/conversations/${id}`, { method: "DELETE" });
    } catch { /* ignore */ }
    if (activeId === id) newChat();
    loadConvs();
  }

  type Attach = { name: string; kind: "image" | "document"; media_type: string; data: string };
  const [attachments, setAttachments] = useState<Attach[]>([]);
  const fileRef = useRef<HTMLInputElement>(null);

  async function onFiles(files: FileList | null) {
    if (!files) return;
    const list: Attach[] = [];
    for (const f of Array.from(files).slice(0, 5)) {
      const data = await new Promise<string>((res, rej) => {
        const r = new FileReader();
        r.onload = () => res(String(r.result).split(",")[1] || "");
        r.onerror = rej;
        r.readAsDataURL(f);
      });
      list.push({
        name: f.name,
        kind: f.type.startsWith("image/") ? "image" : "document",
        media_type: f.type || "application/octet-stream",
        data,
      });
    }
    setAttachments((prev) => [...prev, ...list].slice(0, 5));
    if (fileRef.current) fileRef.current.value = "";
  }

  async function send(text: string) {
    const q = text.trim();
    if ((!q && attachments.length === 0) || loading) return;
    const shown = q || "(lampiran)";
    const next = [...messages, { role: "user", content: shown } as Msg];
    setMessages(next);
    setInput("");
    if (taRef.current) taRef.current.style.height = "auto";
    const sendAtt = attachments.map((a) => ({ kind: a.kind, media_type: a.media_type, data: a.data }));
    setAttachments([]);
    setLoading(true);
    try {
      const res = await api<{ conversation_id: string; title: string; reply: string }>(
        "/ai/chat",
        {
          method: "POST",
          body: JSON.stringify({
            conversation_id: activeId,
            message: q || "Tolong analisis lampiran ini.",
            model,
            effort,
            attachments: sendAtt.length ? sendAtt : undefined,
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
          <div className="px-3 pt-4">
            <button
              onClick={newChat}
              className="flex w-full items-center gap-2 rounded-[var(--radius-button)] border border-line bg-surface px-3 py-2.5 text-sm font-medium text-ink shadow-[var(--shadow-pop)] transition-colors hover:border-primary hover:bg-[var(--primary-soft)]"
            >
              <Plus size={16} className="text-primary" />
              Percakapan baru
            </button>
          </div>
          <p className="px-5 pb-1 pt-5 text-caption font-medium uppercase tracking-wide text-ink-subtle">
            Riwayat
          </p>
          <div className="flex-1 space-y-0.5 overflow-y-auto px-2 pb-4">
            {convs.length === 0 && (
              <p className="px-3 py-3 text-sm text-ink-subtle">Belum ada percakapan.</p>
            )}
            {convs.map((c) => (
              <div
                key={c.id}
                onClick={() => openConv(c.id)}
                className={`group flex cursor-pointer items-center gap-2 rounded-[var(--radius-input)] px-3 py-2 text-sm transition-colors ${
                  activeId === c.id
                    ? "bg-[var(--primary-soft)] font-medium text-ink"
                    : "text-ink-muted hover:bg-surface-sunken"
                }`}
              >
                <span className="flex-1 truncate">{c.title}</span>
                <button
                  onClick={(e) => removeConv(c.id, e)}
                  aria-label="Hapus"
                  className="shrink-0 rounded p-0.5 text-ink-subtle opacity-0 transition-opacity hover:text-danger group-hover:opacity-100"
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
            className="hidden rounded-[var(--radius-input)] p-2 text-ink-muted transition-colors hover:bg-surface-sunken md:block"
          >
            <PanelLeft size={18} />
          </button>
          <span className="grid h-9 w-9 place-items-center rounded-full bg-[var(--primary-soft)] text-primary">
            <Sparkles size={17} />
          </span>
          <div className="flex-1 leading-tight">
            <h1 className="font-display text-[15px] font-bold text-ink">Asisten AI</h1>
            <p className="text-caption text-ink-subtle">Berbasis data Ananta</p>
          </div>
          <div className="flex items-center gap-2">
            <Select value={model} onChange={setModel} options={models} />
            <Select value={effort} onChange={setEffort} options={efforts} />
          </div>
        </header>

        {/* Thread */}
        <div ref={scrollRef} className="flex-1 overflow-y-auto">
          <div className="mx-auto w-full max-w-3xl px-4 py-8">
            {empty ? (
              <div className="mx-auto mt-8 flex max-w-xl flex-col items-center text-center">
                <span className="grid h-16 w-16 place-items-center rounded-2xl bg-[var(--primary-soft)] text-primary shadow-[var(--shadow-pop)]">
                  <Sparkles size={28} />
                </span>
                <h2 className="mt-5 font-display text-2xl font-bold text-ink">
                  Ada yang bisa dibantu?
                </h2>
                <p className="mt-2 max-w-md text-sm leading-relaxed text-ink-muted">
                  Tanyakan apa saja tentang keuangan bisnismu. Asisten membaca data riil
                  — laba rugi, piutang, stok — untuk menjawab.
                </p>
                <div className="mt-7 grid w-full gap-2.5 sm:grid-cols-2">
                  {CONTOH.map((c) => (
                    <button
                      key={c}
                      onClick={() => send(c)}
                      className="rounded-[var(--radius-button)] border border-line bg-surface px-4 py-3 text-left text-sm text-ink shadow-[var(--shadow-pop)] transition-all hover:-translate-y-0.5 hover:border-primary"
                    >
                      {c}
                    </button>
                  ))}
                </div>
              </div>
            ) : (
              <div className="flex flex-col gap-6">
                {messages.map((m, i) => (
                  <Bubble key={i} msg={m} />
                ))}
                {loading && <Thinking />}
              </div>
            )}
          </div>
        </div>

        {/* Composer */}
        <div className="bg-gradient-to-t from-[var(--canvas)] to-transparent px-4 pb-4 pt-2">
          <div className="mx-auto w-full max-w-3xl">
            {attachments.length > 0 && (
              <div className="mb-2 flex flex-wrap gap-2">
                {attachments.map((a, i) => (
                  <span
                    key={i}
                    className="flex items-center gap-1.5 rounded-[var(--radius-input)] border border-line bg-surface px-2.5 py-1 text-caption text-ink-muted"
                  >
                    <Paperclip size={12} />
                    <span className="max-w-[160px] truncate">{a.name}</span>
                    <button
                      onClick={() => setAttachments((p) => p.filter((_, j) => j !== i))}
                      aria-label="Hapus lampiran"
                      className="text-ink-subtle hover:text-danger"
                    >
                      <X size={12} />
                    </button>
                  </span>
                ))}
              </div>
            )}
            <div className="flex items-end gap-2 rounded-2xl border border-line bg-surface px-3 py-2 shadow-[var(--shadow-pop)] transition-colors focus-within:border-primary">
              <input
                ref={fileRef}
                type="file"
                multiple
                accept="image/*,application/pdf"
                className="hidden"
                onChange={(e) => onFiles(e.target.files)}
              />
              <button
                onClick={() => fileRef.current?.click()}
                aria-label="Lampirkan file"
                className="grid h-9 w-9 shrink-0 place-items-center rounded-full text-ink-muted transition-colors hover:bg-surface-sunken"
              >
                <Paperclip size={17} />
              </button>
              <textarea
                ref={taRef}
                rows={1}
                value={input}
                onChange={(e) => { setInput(e.target.value); grow(); }}
                onKeyDown={onKey}
                placeholder="Tulis pertanyaan…"
                className="max-h-[200px] flex-1 resize-none bg-transparent py-1.5 text-[15px] text-ink outline-none placeholder:text-ink-subtle"
              />
              <button
                onClick={() => send(input)}
                disabled={(!input.trim() && attachments.length === 0) || loading}
                aria-label="Kirim"
                className="grid h-9 w-9 shrink-0 place-items-center rounded-full bg-primary text-white transition-colors hover:bg-[var(--primary-hover)] disabled:opacity-40"
              >
                <ArrowUp size={17} />
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

function Select({ value, onChange, options }: {
  value: string; onChange: (v: string) => void; options: Opt[];
}) {
  return (
    <div className="relative">
      <select
        value={value}
        onChange={(e) => onChange(e.target.value)}
        className="appearance-none rounded-[var(--radius-input)] border border-line bg-surface py-1.5 pl-3 pr-7 text-caption text-ink-muted outline-none transition-colors hover:border-primary focus:border-primary"
      >
        {options.map((o) => (
          <option key={o.id} value={o.id}>{o.label}</option>
        ))}
      </select>
      <ChevronDown
        size={13}
        className="pointer-events-none absolute right-2 top-1/2 -translate-y-1/2 text-ink-subtle"
      />
    </div>
  );
}

function Avatar() {
  return (
    <span className="mt-0.5 grid h-7 w-7 shrink-0 place-items-center rounded-full bg-[var(--primary-soft)] text-primary">
      <Sparkles size={15} />
    </span>
  );
}

function Bubble({ msg }: { msg: Msg }) {
  if (msg.role === "user") {
    return (
      <div className="flex justify-end">
        <div className="max-w-[82%] whitespace-pre-wrap rounded-2xl bg-[var(--primary-soft)] px-4 py-2.5 text-[15px] leading-relaxed text-ink">
          {msg.content}
        </div>
      </div>
    );
  }
  return (
    <div className="flex gap-3">
      <Avatar />
      <div className="min-w-0 flex-1 whitespace-pre-wrap pt-0.5 text-[15px] leading-relaxed text-ink">
        {msg.content}
      </div>
    </div>
  );
}

function Thinking() {
  return (
    <div className="flex gap-3">
      <Avatar />
      <div className="flex items-center gap-1.5 pt-2.5">
        {["0ms", "160ms", "320ms"].map((d) => (
          <span
            key={d}
            className="h-1.5 w-1.5 animate-bounce rounded-full bg-primary"
            style={{ animationDelay: d }}
          />
        ))}
      </div>
    </div>
  );
}

"use client";
import {
  InputHTMLAttributes,
  SelectHTMLAttributes,
  TextareaHTMLAttributes,
  forwardRef,
  ReactNode,
} from "react";

/** Label + slot untuk satu field form. */
export function Field({
  label,
  hint,
  children,
}: {
  label: string;
  hint?: string;
  children: ReactNode;
}) {
  return (
    <label className="block">
      <span className="mb-1 block text-sm font-medium text-ink">{label}</span>
      {children}
      {hint && <span className="mt-1 block text-caption text-ink-subtle">{hint}</span>}
    </label>
  );
}

const fieldBase =
  "w-full rounded-[var(--radius-input)] border border-line bg-surface-sunken px-3 py-2 text-sm text-ink placeholder:text-ink-subtle focus:border-primary focus:bg-surface focus:outline-none";

export const Select = forwardRef<
  HTMLSelectElement,
  SelectHTMLAttributes<HTMLSelectElement>
>(({ className = "", ...props }, ref) => (
  <select ref={ref} className={`${fieldBase} ${className}`} {...props} />
));
Select.displayName = "Select";

export const Textarea = forwardRef<
  HTMLTextAreaElement,
  TextareaHTMLAttributes<HTMLTextAreaElement>
>(({ className = "", ...props }, ref) => (
  <textarea ref={ref} className={`${fieldBase} ${className}`} {...props} />
));
Textarea.displayName = "Textarea";

/** Input angka kecil khusus tabel baris (rata kanan, tabular). */
export const NumCell = forwardRef<
  HTMLInputElement,
  InputHTMLAttributes<HTMLInputElement>
>(({ className = "", ...props }, ref) => (
  <input
    ref={ref}
    inputMode="decimal"
    className={`w-full rounded-[var(--radius-input)] border border-line bg-surface-sunken px-2 py-1.5 text-right text-sm tabular-nums text-ink focus:border-primary focus:bg-surface focus:outline-none ${className}`}
    {...props}
  />
));
NumCell.displayName = "NumCell";

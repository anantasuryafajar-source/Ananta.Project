"use client";
import { InputHTMLAttributes, forwardRef, useState } from "react";
import { Eye, EyeOff } from "lucide-react";

/**
 * Input kata sandi dengan tombol mata untuk menampilkan/menyembunyikan.
 * Dipakai menggantikan <Input type="password" /> di seluruh form sandi.
 */
export const PasswordInput = forwardRef<
  HTMLInputElement,
  Omit<InputHTMLAttributes<HTMLInputElement>, "type">
>(({ className = "", ...props }, ref) => {
  const [show, setShow] = useState(false);
  return (
    <div className="relative">
      <input
        ref={ref}
        type={show ? "text" : "password"}
        className={`w-full rounded-[var(--radius-input)] border border-line bg-surface-sunken px-3 py-2 pr-10 text-sm text-ink placeholder:text-ink-subtle focus:border-primary focus:bg-surface focus:outline-none ${className}`}
        {...props}
      />
      <button
        type="button"
        onClick={() => setShow((v) => !v)}
        tabIndex={-1}
        aria-label={show ? "Sembunyikan kata sandi" : "Tampilkan kata sandi"}
        className="absolute inset-y-0 right-0 grid w-10 place-items-center text-ink-subtle transition-colors hover:text-ink"
      >
        {show ? <EyeOff size={16} /> : <Eye size={16} />}
      </button>
    </div>
  );
});
PasswordInput.displayName = "PasswordInput";

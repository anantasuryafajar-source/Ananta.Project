"use client";
import { ButtonHTMLAttributes, forwardRef } from "react";

type Variant = "primary" | "secondary" | "ghost" | "danger";

const styles: Record<Variant, string> = {
  primary:
    "bg-primary text-white hover:bg-[var(--primary-hover)] disabled:opacity-50",
  secondary:
    "bg-surface text-ink border border-line hover:bg-surface-sunken",
  ghost: "text-ink-muted hover:bg-surface-sunken",
  danger: "bg-danger text-white hover:opacity-90",
};

interface Props extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: Variant;
}

export const Button = forwardRef<HTMLButtonElement, Props>(
  ({ variant = "primary", className = "", ...props }, ref) => (
    <button
      ref={ref}
      className={`inline-flex items-center justify-center gap-2 rounded-[var(--radius-button)] px-4 py-2 text-sm font-medium transition-colors duration-150 focus-visible:outline focus-visible:outline-2 focus-visible:outline-[var(--ring)] ${styles[variant]} ${className}`}
      {...props}
    />
  ),
);
Button.displayName = "Button";

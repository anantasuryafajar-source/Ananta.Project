// Elemen khas Ananta: garis "arus transaksi tanpa putus". Subtil, satu warna.
export function ContinuityRibbon({ className = "" }: { className?: string }) {
  return (
    <svg
      viewBox="0 0 240 24"
      className={className}
      fill="none"
      aria-hidden
      style={{ width: "100%", height: 24 }}
    >
      <path
        d="M0 12 C 40 2, 60 22, 100 12 S 160 2, 200 12 S 240 22, 240 12"
        stroke="var(--primary)"
        strokeOpacity="0.35"
        strokeWidth="2"
        strokeLinecap="round"
      />
    </svg>
  );
}

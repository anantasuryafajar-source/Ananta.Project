import { Card } from "../ui/card";

export function KpiCard({
  label, value, hint, negative = false,
}: {
  label: string; value: string; hint?: string; negative?: boolean;
}) {
  return (
    <Card>
      <p className="text-caption text-ink-muted">{label}</p>
      <p className={`num mt-2 text-2xl font-semibold ${negative ? "num-neg" : "text-ink"}`}>
        {value}
      </p>
      {hint && <p className="mt-1 text-caption text-ink-subtle">{hint}</p>}
    </Card>
  );
}

import type { ReactNode } from "react";
import { DEMO_DISCLAIMER } from "@/lib/search/types";

export type StatusLevel =
  | "validated"
  | "ready"
  | "pending"
  | "unavailable"
  | "next"
  | "planned"
  | "exploratory";

const statusStyles: Record<StatusLevel, { label: string; className: string }> = {
  validated: {
    label: "Validated",
    className: "border-emerald-300 bg-emerald-50 text-emerald-800",
  },
  ready: {
    label: "Ready",
    className: "border-blue-300 bg-blue-50 text-blue-800",
  },
  pending: {
    label: "Pending",
    className: "border-amber-300 bg-amber-50 text-amber-900",
  },
  unavailable: {
    label: "Unavailable",
    className: "border-slate-300 bg-slate-50 text-slate-700",
  },
  next: {
    label: "Next",
    className: "border-blue-300 bg-blue-50 text-blue-800",
  },
  planned: {
    label: "Planned",
    className: "border-ink/10 bg-white/70 text-ink/70",
  },
  exploratory: {
    label: "Exploratory",
    className: "border-violet/20 bg-violet/10 text-violet",
  },
};

export function StatusBadge({ status }: { status: StatusLevel | string }) {
  const item = statusStyles[(status as StatusLevel) in statusStyles ? (status as StatusLevel) : "pending"];
  return (
    <span
      className={`inline-flex min-h-7 items-center gap-1.5 rounded-full border px-2.5 py-1 text-xs font-semibold ${item.className}`}
    >
      <span className="h-1.5 w-1.5 rounded-full bg-current" aria-hidden="true" />
      {item.label}
    </span>
  );
}

export function MetricCard({
  label,
  value,
  hint,
  mono = false,
}: {
  label: string;
  value: ReactNode;
  hint?: ReactNode;
  mono?: boolean;
}) {
  return (
    <div className="card-soft p-5">
      <dt className="text-xs font-semibold uppercase tracking-[0.18em] text-ink/55">{label}</dt>
      <dd className={`mt-2 text-3xl font-semibold text-ink ${mono ? "font-mono" : "font-display"}`}>
        {value}
      </dd>
      {hint ? <p className="mt-1.5 text-xs leading-5 text-ink/55">{hint}</p> : null}
    </div>
  );
}

export function Section({
  id,
  eyebrow,
  title,
  intro,
  children,
}: {
  id?: string;
  eyebrow?: string;
  title: string;
  intro?: ReactNode;
  children: ReactNode;
}) {
  return (
    <section id={id} className="scroll-mt-24 py-14 md:py-20">
      <div className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8">
        {eyebrow ? (
          <p className="text-xs font-semibold uppercase tracking-[0.18em] text-teal">{eyebrow}</p>
        ) : null}
        <h2 className="mt-2 text-3xl font-semibold leading-tight text-ink md:text-4xl">{title}</h2>
        {intro ? <p className="mt-3 max-w-3xl text-base leading-7 text-ink/65">{intro}</p> : null}
        <div className="mt-8">{children}</div>
      </div>
    </section>
  );
}

export function LimitationAlert({
  children,
  tone = "warning",
}: {
  children: ReactNode;
  tone?: "warning" | "info";
}) {
  const className =
    tone === "warning"
      ? "border-amber-300 bg-amber-50 text-amber-950"
      : "border-blue-200 bg-blue-50 text-blue-950";
  return (
    <div role="note" className={`rounded-lg border p-4 text-sm leading-6 ${className}`}>
      {children}
    </div>
  );
}

export function SyntheticDisclaimer({ compact = false }: { compact?: boolean }) {
  return (
    <div
      className={`inline-flex items-center gap-2 rounded-full border border-amber-300 bg-amber-50 font-semibold text-amber-900 ${
        compact ? "px-2.5 py-1 text-[0.68rem]" : "px-3 py-1.5 text-xs"
      }`}
      role="status"
    >
      <span aria-hidden="true">●</span>
      {DEMO_DISCLAIMER}
    </div>
  );
}

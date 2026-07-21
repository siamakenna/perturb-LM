import type { Metadata } from "next";
import Link from "next/link";
import { ArrowRight, Github, ShieldCheck } from "lucide-react";
import summary from "@/data/project-summary.json";
import {
  LimitationAlert,
  MetricCard,
  Section,
  StatusBadge,
  SyntheticDisclaimer,
} from "@/components/perturb/primitives";

export const metadata: Metadata = {
  title: "Benchmark Dashboard",
  description:
    "Perturb-LM benchmark dashboard with public-safe aggregate metrics, leakage controls, split readiness, and pending model states.",
};

export default function DashboardPage() {
  return (
    <main id="main" className="pb-10">
      <section className="relative overflow-hidden border-b border-ink/10">
        <div className="grid-field absolute inset-0 opacity-40" aria-hidden="true" />
        <div className="wells-field absolute inset-y-0 right-0 hidden w-1/2 opacity-70 lg:block" aria-hidden="true" />
        <div className="relative mx-auto max-w-7xl px-4 py-12 sm:px-6 md:py-16 lg:px-8">
          <div className="flex flex-wrap items-start justify-between gap-4">
            <div>
              <p className="text-xs font-semibold uppercase tracking-[0.18em] text-teal">Dashboard</p>
              <h1 className="mt-2 text-4xl font-semibold leading-tight text-ink md:text-5xl">
                Benchmark status
              </h1>
              <p className="mt-4 max-w-3xl text-base leading-7 text-ink/68">
                The Perturb-LM validation ladder. Only baseline rows with completed
                controls show numeric scores; frozen and projected encoder rows remain
                pending until real runs are executed and reviewed.
              </p>
            </div>
            <SyntheticDisclaimer />
          </div>
          <div className="mt-6 max-w-4xl">
            <LimitationAlert>
              <strong>{summary.syntheticDisclaimer}.</strong> This dashboard reflects
              benchmark scaffolding and completed baseline controls. No BiomedBERT,
              linear-projection, replicate-consensus, or held-out-batch model scores are shown.
            </LimitationAlert>
          </div>
          <div className="mt-6 flex flex-wrap gap-3">
            <Link
              href="/demo"
              className="inline-flex min-h-11 items-center gap-2 rounded-md bg-ink px-4 text-sm font-semibold text-white hover:bg-slate-800"
            >
              Open synthetic demo <ArrowRight className="h-4 w-4" />
            </Link>
            <Link
              href="https://github.com/siamakenna/perturb-LM"
              className="inline-flex min-h-11 items-center gap-2 rounded-md border border-ink/15 bg-white/70 px-4 text-sm font-semibold text-ink hover:bg-white"
            >
              GitHub <Github className="h-4 w-4" />
            </Link>
          </div>
        </div>
      </section>

      <Section id="status" eyebrow="Current status" title="Where the project stands">
        <div className="grid gap-3 md:grid-cols-2">
          {summary.researchStatus.map((item) => (
            <article key={item.key} className="card-soft flex items-start justify-between gap-4 p-4">
              <div>
                <h2 className="font-display text-lg font-semibold text-ink">{item.label}</h2>
                <p className="mt-1 text-sm leading-6 text-ink/62">{item.detail}</p>
              </div>
              <StatusBadge status={item.status} />
            </article>
          ))}
        </div>
      </Section>

      <Section id="overview" eyebrow="Benchmark overview" title="Public-safe aggregates only">
        <dl className="grid gap-4 md:grid-cols-3">
          <MetricCard label="Profiles" value={summary.profileCount.toLocaleString()} mono />
          <MetricCard label="Features" value={summary.featureCount.toLocaleString()} mono />
          <MetricCard label="Queries" value={summary.queryCount.toLocaleString()} mono />
          <MetricCard
            label="TF-IDF mAP"
            value={summary.lexicalBaselineMap.toFixed(4)}
            mono
            hint={summary.lexicalBaselineName}
          />
          <MetricCard
            label="95% CI"
            value={`${summary.confidenceInterval.low.toFixed(4)} to ${summary.confidenceInterval.high.toFixed(4)}`}
            mono
            hint={summary.confidenceInterval.level}
          />
          <MetricCard
            label="Model status"
            value={<span className="text-xl capitalize">{summary.learnedModelStatus}</span>}
            hint="No learned model result is public."
          />
        </dl>
      </Section>

      <Section
        id="comparison"
        eyebrow="Method comparison"
        title="Pending rows do not render scores"
        intro="Charts and tables use the same public-safe source. A method with no completed result shows a pending badge and no fabricated bar."
      >
        <div className="card-paper overflow-x-auto" role="region" aria-label="Method comparison table">
          <table className="w-full min-w-[760px] text-sm">
            <caption className="sr-only">
              Method comparison table. Pending learned-model rows have no numeric score or bar.
            </caption>
            <thead className="bg-white/60 text-left text-xs uppercase tracking-[0.16em] text-ink/55">
              <tr>
                <th scope="col" className="px-4 py-3 font-semibold">Method</th>
                <th scope="col" className="px-4 py-3 font-semibold">mAP</th>
                <th scope="col" className="px-4 py-3 font-semibold">95% CI</th>
                <th scope="col" className="px-4 py-3 font-semibold">Status note</th>
              </tr>
            </thead>
            <tbody>
              {summary.methodComparison.map((method) => (
                <tr key={method.key} className="border-t border-ink/10 align-middle">
                  <th scope="row" className="px-4 py-4 text-left font-semibold text-ink">
                    {method.label}
                  </th>
                  <td className="px-4 py-4">
                    {method.hasResult && method.map !== null ? (
                      <div className="flex items-center gap-3">
                        <div
                          className="h-2 w-40 overflow-hidden rounded-full bg-ink/10"
                          aria-hidden="true"
                        >
                          <div
                            className="h-full rounded-full bg-teal"
                            style={{ width: `${Math.min(100, Math.round(method.map * 100))}%` }}
                          />
                        </div>
                        <span className="font-mono text-sm text-ink">{method.map.toFixed(4)}</span>
                      </div>
                    ) : (
                      <StatusBadge status="pending" />
                    )}
                  </td>
                  <td className="px-4 py-4 font-mono text-xs text-ink/58">
                    {method.hasResult && method.ciLow !== null && method.ciHigh !== null
                      ? `${method.ciLow.toFixed(4)} to ${method.ciHigh.toFixed(4)}`
                      : "not available"}
                  </td>
                  <td className="px-4 py-4 text-ink/65">{method.note}</td>
                </tr>
              ))}
            </tbody>
          </table>
          <p className="border-t border-ink/10 px-4 py-3 text-xs leading-5 text-ink/55">
            Text equivalent: identifier-stripped TF-IDF is the primary baseline at{" "}
            {summary.lexicalBaselineMap.toFixed(4)} mAP. Learned-model rows are pending and
            intentionally have no numeric score.
          </p>
        </div>
      </Section>

      <Section
        id="splits"
        eyebrow="Split and filter readiness"
        title="Each condition must report its own query counts"
        intro="The dashboard shows configured readiness only. It does not reuse the full 641-query count as if every split-specific model run had completed."
      >
        <div className="grid gap-3 md:grid-cols-2">
          {summary.splitReadiness.map((item) => (
            <article key={item.key} className="card-soft flex items-start justify-between gap-4 p-4">
              <div>
                <h2 className="font-display text-lg font-semibold text-ink">{item.label}</h2>
                <p className="mt-1 text-sm leading-6 text-ink/62">{item.detail}</p>
              </div>
              <StatusBadge status={item.status} />
            </article>
          ))}
        </div>
      </Section>

      <Section id="leakage" eyebrow="Leakage controls" title="Controls enforced before stronger claims">
        <ul className="grid gap-3 md:grid-cols-2">
          {summary.leakageControls.map((item) => (
            <li key={item} className="card-paper flex items-start gap-3 p-4 text-sm leading-6 text-ink/70">
              <ShieldCheck className="mt-0.5 h-4 w-4 flex-none text-teal" aria-hidden="true" />
              <span>{item}</span>
            </li>
          ))}
        </ul>
      </Section>

      <Section id="roadmap" eyebrow="Phase 3C roadmap" title="Next experiments, still gated">
        <ol className="grid gap-3 md:grid-cols-2">
          {summary.roadmap.map((item, index) => (
            <li key={item.key} className="card-soft flex gap-4 p-4">
              <span className="font-mono text-xs text-ink/45">{String(index + 1).padStart(2, "0")}</span>
              <div className="flex-1">
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <h2 className="font-display text-lg font-semibold text-ink">{item.label}</h2>
                  <StatusBadge status={item.status} />
                </div>
                <p className="mt-1 text-sm leading-6 text-ink/62">{item.detail}</p>
              </div>
            </li>
          ))}
        </ol>
      </Section>

      <Section id="limitations" eyebrow="Limitations" title="What this dashboard does not claim">
        <LimitationAlert tone="info">
          <ul className="grid gap-2 md:grid-cols-2">
            {summary.knownLimitations.map((item) => (
              <li key={item} className="flex gap-2">
                <span aria-hidden="true">•</span>
                <span>{item}</span>
              </li>
            ))}
          </ul>
        </LimitationAlert>
      </Section>
    </main>
  );
}

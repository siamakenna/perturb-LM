import Link from "next/link";
import { ArrowRight, CheckCircle2, FlaskConical, ShieldCheck, TriangleAlert } from "lucide-react";
import summary from "@/data/project-summary.json";
import { Badge } from "@/components/ui/badge";
import { Card } from "@/components/ui/card";
import { Separator } from "@/components/ui/separator";

const benchmarkCards = [
  { label: "profiles", value: summary.profileCount.toLocaleString() },
  { label: "morphology features", value: summary.featureCount.toLocaleString() },
  { label: "full benchmark queries", value: summary.queryCount.toLocaleString() },
  { label: "identifier-stripped TF-IDF mAP", value: summary.lexicalBaselineMap.toFixed(4) },
];

const pipeline = [
  ["Biological language query", "Researcher describes a phenotype or mechanism."],
  ["Frozen text representation", "The real biomedical encoder evaluation is pending."],
  ["Lightweight alignment", "A small projection is the next controlled experiment."],
  ["Morphology-profile retrieval", "Profile-space ranking before any image-level claim."],
  ["Perturbation-level evaluation", "Metrics aggregate at the perturbation level."],
];

export default function HomePage() {
  return (
    <main id="overview">
      <section className="relative overflow-hidden">
        <div className="micro-dot-field absolute inset-x-0 top-0 h-96 opacity-60" aria-hidden="true" />
        <div className="section-entry relative mx-auto grid max-w-7xl gap-12 px-4 py-20 sm:px-6 lg:grid-cols-[1.05fr_0.95fr] lg:px-8 lg:py-28">
          <div>
            <div className="mb-6 flex flex-wrap gap-2">
              {["Controlled benchmark", "CPJUMP1 profiles", "Open-source research", "Model evaluation pending"].map(
                (label) => (
                  <Badge key={label}>{label}</Badge>
                ),
              )}
            </div>
            <h1 className="max-w-4xl text-5xl font-semibold leading-tight tracking-normal text-ink sm:text-6xl">
              Search perturbation-induced morphology with biological language
            </h1>
            <p className="mt-6 max-w-2xl text-lg leading-8 text-ink/70">
              Perturb-LM is currently a text-to-morphology benchmark. It validates
              leakage-aware retrieval over Cell Painting profiles while keeping
              image-level retrieval as a longer-term direction.
            </p>
            <div className="mt-8 flex flex-wrap gap-3">
              <Link
                href="/demo"
                className="inline-flex h-12 items-center gap-2 rounded-md bg-ink px-5 text-sm font-semibold text-white shadow-soft transition hover:bg-slate-800"
              >
                Try the illustrative demo <ArrowRight className="h-4 w-4" />
              </Link>
              <Link
                href="/methods"
                className="inline-flex h-12 items-center rounded-md border border-ink/15 bg-white/70 px-5 text-sm font-semibold text-ink transition hover:bg-white"
              >
                Read methods overview
              </Link>
            </div>
          </div>
          <Card className="bg-white/80">
            <p className="text-sm font-semibold uppercase tracking-[0.2em] text-teal">Research question</p>
            <blockquote className="mt-4 text-2xl font-semibold leading-snug text-ink">
              Can frozen biomedical language representations retrieve
              perturbation-induced cellular morphology better than strong
              identifier-stripped lexical controls?
            </blockquote>
            <Separator />
            <div className="mt-6 grid gap-3 sm:grid-cols-2">
              {benchmarkCards.map((card) => (
                <div key={card.label} className="rounded-md border border-ink/10 bg-paper/70 p-4">
                  <div className="text-3xl font-semibold text-ink">{card.value}</div>
                  <div className="mt-1 text-sm text-ink/65">{card.label}</div>
                </div>
              ))}
            </div>
            <p className="mt-4 text-sm text-ink/60">
              mAP 95% query-bootstrap CI: {summary.confidenceInterval.low.toFixed(4)} to{" "}
              {summary.confidenceInterval.high.toFixed(4)}. This is a lexical
              control, not a learned-model result.
            </p>
          </Card>
        </div>
      </section>

      <section id="why-leakage" className="mx-auto max-w-7xl px-4 py-16 sm:px-6 lg:px-8">
        <div className="grid gap-8 lg:grid-cols-[0.8fr_1.2fr]">
          <div>
            <h2 className="text-3xl font-semibold text-ink">Why leakage matters</h2>
            <p className="mt-4 text-ink/70">
              Treatment names, target sequences, plates, wells, and replicates can
              make retrieval look stronger than it is. Perturb-LM treats those
              shortcuts as measurable failure modes.
            </p>
          </div>
          <div className="grid gap-4 md:grid-cols-2">
            <Card>
              <TriangleAlert className="h-6 w-6 text-violet" />
              <h3 className="mt-4 text-xl font-semibold">Naive evaluation</h3>
              <p className="mt-2 text-sm leading-6 text-ink/65">
                Can reward exact treatment identifiers, target sequences, replicate
                structure, and acquisition artifacts.
              </p>
            </Card>
            <Card>
              <ShieldCheck className="h-6 w-6 text-teal" />
              <h3 className="mt-4 text-xl font-semibold">Leakage-aware evaluation</h3>
              <p className="mt-2 text-sm leading-6 text-ink/65">
                Removes identifiers, reports evaluable queries, and tests held-out
                and plate/well-aware conditions.
              </p>
            </Card>
          </div>
        </div>
      </section>

      <section id="benchmark" className="bg-white/45 py-16">
        <div className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8">
          <h2 className="text-3xl font-semibold text-ink">How the system works</h2>
          <div className="mt-8 grid gap-4 lg:grid-cols-5">
            {pipeline.map(([title, copy], index) => (
              <Card key={title} className="shadow-none">
                <div className="grid h-9 w-9 place-items-center rounded-md bg-teal/10 text-sm font-bold text-teal">
                  {index + 1}
                </div>
                <h3 className="mt-4 font-semibold text-ink">{title}</h3>
                <p className="mt-2 text-sm leading-6 text-ink/65">{copy}</p>
              </Card>
            ))}
          </div>
        </div>
      </section>

      <section className="mx-auto grid max-w-7xl gap-6 px-4 py-16 sm:px-6 lg:grid-cols-3 lg:px-8">
        {[
          ["Validated foundation", "QC, leakage checks, deterministic queries, train-only preprocessing, and reproducible smoke workflows are in place."],
          ["Lexical benchmark", "Identifier-stripped TF-IDF establishes the primary lexical control that future models must beat."],
          ["Pending learned model", "Frozen text embeddings and a lightweight projection are the next experiment, not a completed result."],
        ].map(([title, copy]) => (
          <Card key={title}>
            <CheckCircle2 className="h-6 w-6 text-teal" />
            <h3 className="mt-4 text-xl font-semibold">{title}</h3>
            <p className="mt-2 text-sm leading-6 text-ink/65">{copy}</p>
          </Card>
        ))}
      </section>

      <section className="mx-auto max-w-7xl px-4 pb-16 sm:px-6 lg:px-8">
        <div className="grid gap-8 lg:grid-cols-2">
          <Card>
            <h2 className="text-2xl font-semibold">Current limitations</h2>
            <ul className="mt-5 space-y-3 text-sm leading-6 text-ink/70">
              {summary.knownLimitations.map((item) => (
                <li key={item} className="flex gap-3">
                  <span className="mt-2 h-1.5 w-1.5 rounded-full bg-violet" aria-hidden="true" />
                  <span>{item}</span>
                </li>
              ))}
            </ul>
          </Card>
          <Card>
            <h2 className="text-2xl font-semibold">Roadmap</h2>
            <div className="mt-5 grid gap-3 text-sm text-ink/70">
              {[
                "Frozen embedding baseline",
                "Regularized linear projection",
                "Replicate consensus",
                "Hard negatives",
                "Second-batch harmonization",
                "Image linkage",
                "Interpretable morphology attribution",
              ].map((item) => (
                <div key={item} className="rounded-md bg-paper/80 px-3 py-2">{item}</div>
              ))}
            </div>
          </Card>
        </div>
      </section>

      <footer className="border-t border-ink/10 px-4 py-10 sm:px-6 lg:px-8">
        <div className="mx-auto flex max-w-7xl flex-col gap-4 text-sm text-ink/60 md:flex-row md:items-center md:justify-between">
          <div className="flex items-center gap-2">
            <FlaskConical className="h-4 w-4" />
            <span>Research prototype. Model evaluation pending.</span>
          </div>
          <div className="flex flex-wrap gap-4">
            <Link href="/methods" className="hover:text-ink">Methods</Link>
            <Link href="/demo" className="hover:text-ink">Prototype</Link>
            <Link href="https://github.com/siamakenna/perturb-LM" className="hover:text-ink">
              Repository
            </Link>
          </div>
        </div>
      </footer>
    </main>
  );
}

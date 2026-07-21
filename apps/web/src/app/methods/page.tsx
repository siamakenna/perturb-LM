import type { Metadata } from "next";
import summary from "@/data/project-summary.json";
import { Card } from "@/components/ui/card";

export const metadata: Metadata = {
  title: "Methods Overview",
  description:
    "A public methods overview for the Perturb-LM leakage-aware morphology retrieval benchmark.",
};

const sections = [
  [
    "Objective",
    "Perturb-LM evaluates whether biological language can retrieve perturbation-induced Cell Painting morphology under leakage-aware, perturbation-level evaluation.",
  ],
  [
    "Dataset inventory",
    "The primary benchmark uses 4,524 CPJUMP1 morphology profiles in a consistent 904-feature feature space. A larger compatibility investigation is not the primary modeling dataset.",
  ],
  [
    "Identifier policy",
    "Target sequences and direct treatment identifiers are prohibited from identifier-stripped query and candidate text. The primary lexical control uses gene, perturbation type, control type, and negative-control type only.",
  ],
  [
    "Controls",
    "The benchmark reports full-metadata TF-IDF as an identifier-dominated reference, identifier-stripped TF-IDF as the main lexical control, plus random and shuffled-label controls.",
  ],
  [
    "Evaluation",
    "Metrics are reported at the perturbation level with total query counts, evaluable query counts, Hit@K, Recall@K, mAP, enrichment over random, and query-bootstrap uncertainty.",
  ],
  [
    "Next experiment",
    "The planned model test freezes a biomedical text encoder and trains a lightweight projection into the morphology-profile space. Learned model results are pending.",
  ],
];

export default function MethodsPage() {
  return (
    <main id="main" className="mx-auto max-w-5xl px-4 py-16 sm:px-6 lg:px-8">
      <h1 className="text-5xl font-semibold leading-tight">Methods overview</h1>
      <p className="mt-5 max-w-3xl text-lg leading-8 text-ink/70">
        This page summarizes the public-safe benchmark methods. It intentionally
        omits local commands, local paths, row-level data, treatment identifiers,
        target sequences, and unpublished model results.
      </p>
      <div className="mt-10 grid gap-5">
        {sections.map(([title, copy]) => (
          <Card key={title} className="shadow-none">
            <h2 className="text-2xl font-semibold">{title}</h2>
            <p className="mt-3 leading-7 text-ink/70">{copy}</p>
          </Card>
        ))}
      </div>
      <Card className="mt-8 border-teal/20 bg-teal/5 shadow-none">
        <h2 className="text-2xl font-semibold">Current benchmark snapshot</h2>
        <dl className="mt-5 grid gap-4 sm:grid-cols-2">
          <div>
            <dt className="text-sm text-ink/55">Profiles</dt>
            <dd className="text-2xl font-semibold">{summary.profileCount.toLocaleString()}</dd>
          </div>
          <div>
            <dt className="text-sm text-ink/55">Morphology features</dt>
            <dd className="text-2xl font-semibold">{summary.featureCount.toLocaleString()}</dd>
          </div>
          <div>
            <dt className="text-sm text-ink/55">Full benchmark queries</dt>
            <dd className="text-2xl font-semibold">{summary.queryCount.toLocaleString()}</dd>
          </div>
          <div>
            <dt className="text-sm text-ink/55">Model status</dt>
            <dd className="text-2xl font-semibold capitalize">{summary.learnedModelStatus}</dd>
          </div>
        </dl>
      </Card>
    </main>
  );
}

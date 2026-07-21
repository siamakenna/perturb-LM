import type { Metadata } from "next";
import { DemoSearch } from "@/components/demo-search";

export const metadata: Metadata = {
  title: "Illustrative Retrieval Demo",
  description:
    "Synthetic interface demo for Perturb-LM. Results are illustrative and not real model output.",
};

export default function DemoPage() {
  return (
    <main id="main" className="mx-auto max-w-7xl px-4 py-12 sm:px-6 md:py-16 lg:px-8">
      <DemoSearch />
    </main>
  );
}

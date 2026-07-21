import type { Metadata } from "next";
import Link from "next/link";
import "./globals.css";

export const metadata: Metadata = {
  metadataBase: new URL("https://perturb-lm.vercel.app"),
  title: {
    default: "Perturb-LM: Leakage-Aware Language Retrieval",
    template: "%s | Perturb-LM",
  },
  description:
    "A leakage-aware benchmark for aligning biomedical language with Cell Painting morphology profiles under perturbation-level and held-out evaluation.",
  applicationName: "Perturb-LM",
  robots: {
    index: true,
    follow: true,
  },
  openGraph: {
    title: "Perturb-LM",
    description:
      "Leakage-aware language retrieval of Cell Painting morphology profiles.",
    type: "website",
    images: ["/og.svg"],
  },
  icons: {
    icon: "/favicon.svg",
  },
};

const navItems = [
  ["Overview", "/#overview"],
  ["Why Leakage Matters", "/#why-leakage"],
  ["Benchmark", "/#benchmark"],
  ["Prototype", "/demo"],
  ["Methods", "/methods"],
  ["GitHub", "https://github.com/siamakenna/perturb-LM"],
];

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body className="min-h-screen font-sans antialiased">
        <header className="sticky top-0 z-40 border-b border-ink/10 bg-paper/90 backdrop-blur">
          <nav className="mx-auto flex max-w-7xl items-center justify-between px-4 py-4 sm:px-6 lg:px-8">
            <Link href="/" className="flex items-center gap-3 font-semibold text-ink">
              <span className="grid h-9 w-9 place-items-center rounded-md bg-ink text-sm text-white">
                PL
              </span>
              <span>Perturb-LM</span>
            </Link>
            <div className="hidden items-center gap-5 text-sm font-medium text-ink/70 lg:flex">
              {navItems.map(([label, href]) => (
                <Link
                  key={label}
                  href={href}
                  className="transition hover:text-ink focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-4 focus-visible:outline-teal"
                >
                  {label}
                </Link>
              ))}
            </div>
            <div className="hidden lg:block">
              <Link
                href="/demo"
                className="rounded-md bg-ink px-4 py-2 text-sm font-semibold text-white transition hover:bg-slate-800 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-teal"
              >
                Demo
              </Link>
            </div>
            <details className="relative lg:hidden">
              <summary className="cursor-pointer list-none rounded-md border border-ink/15 bg-white/80 px-3 py-2 text-sm font-semibold text-ink focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-teal">
                Menu
              </summary>
              <div className="absolute right-0 mt-3 grid w-64 gap-1 rounded-lg border border-ink/10 bg-white p-3 text-sm font-semibold text-ink shadow-soft">
                {navItems.map(([label, href]) => (
                  <Link key={label} href={href} className="rounded-md px-3 py-2 hover:bg-paper">
                    {label}
                  </Link>
                ))}
              </div>
            </details>
          </nav>
        </header>
        {children}
      </body>
    </html>
  );
}

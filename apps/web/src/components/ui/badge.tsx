import { cn } from "@/lib/utils";

export function Badge({ className, children }: React.HTMLAttributes<HTMLSpanElement>) {
  return (
    <span
      className={cn(
        "inline-flex items-center rounded-full border border-ink/10 bg-white/70 px-3 py-1 text-xs font-semibold text-ink/75",
        className,
      )}
    >
      {children}
    </span>
  );
}

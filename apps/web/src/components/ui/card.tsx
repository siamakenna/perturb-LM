import { cn } from "@/lib/utils";

export function Card({ className, ...props }: React.HTMLAttributes<HTMLDivElement>) {
  return (
    <div
      className={cn("rounded-lg border border-ink/10 bg-white/75 p-5 shadow-soft", className)}
      {...props}
    />
  );
}

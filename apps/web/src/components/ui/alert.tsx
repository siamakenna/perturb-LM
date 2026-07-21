import { cn } from "@/lib/utils";

export function Alert({ className, ...props }: React.HTMLAttributes<HTMLDivElement>) {
  return (
    <div
      role="note"
      className={cn("rounded-lg border border-teal/20 bg-teal/5 p-4 text-sm text-ink", className)}
      {...props}
    />
  );
}

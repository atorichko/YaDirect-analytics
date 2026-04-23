import Link from "next/link";
import { CircleHelp } from "lucide-react";

type Props = { className?: string };

export function SiteHelpLink({ className }: Props) {
  return (
    <Link
      href="/help"
      className={
        className ??
        "inline-flex h-9 w-9 shrink-0 items-center justify-center rounded-md border border-input bg-background text-muted-foreground transition-colors hover:bg-accent hover:text-accent-foreground"
      }
      title="Справка: проверки и уровни L1–L3"
      aria-label="Справка по проверкам"
    >
      <CircleHelp className="h-5 w-5" strokeWidth={1.75} />
    </Link>
  );
}

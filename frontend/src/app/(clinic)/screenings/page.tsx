import type { Metadata } from "next";
import { ScreeningsScreen } from "@/components/screenings-screen";
import type { ScreeningQuery } from "@/lib/history";

export const metadata: Metadata = { title: "Past screenings · VISCAN" };

type Params = Record<string, string | undefined>;

const VERDICTS = ["SUSPICIOUS", "NOT_SUSPICIOUS", "INDETERMINATE"] as const;
const STATUSES = ["pending", "reviewed", "disputed"] as const;
const SORTS = ["newest", "oldest", "risk"] as const;

const pick = <T extends string>(value: string | undefined, allowed: readonly T[]) =>
  allowed.includes(value as T) ? (value as T) : undefined;

export default async function ScreeningsPage({ searchParams }: { searchParams: Promise<Params> }) {
  const params = await searchParams;
  const initial: ScreeningQuery = {
    q: params.q || undefined,
    verdict: pick(params.verdict, VERDICTS),
    status: pick(params.status, STATUSES),
    sort: pick(params.sort, SORTS),
    referred: params.referred === "1" || undefined,
    overdue: params.overdue === "1" || undefined,
  };
  const set = Object.fromEntries(Object.entries(initial).filter(([, value]) => value !== undefined));
  return <ScreeningsScreen initial={set} />;
}

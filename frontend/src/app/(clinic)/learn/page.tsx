import type { Metadata } from "next";
import { LearnScreen } from "@/components/learn-screen";

export const metadata: Metadata = { title: "Learn with Kezia · VISCAN" };

export default async function LearnPage({ searchParams }: { searchParams: Promise<{ case?: string }> }) {
  const { case: caseParam } = await searchParams;
  const caseId = Number(caseParam);
  return <LearnScreen initialCaseId={Number.isInteger(caseId) && caseId > 0 ? caseId : null} />;
}

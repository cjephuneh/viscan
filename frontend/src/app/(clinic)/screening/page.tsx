import { redirect } from "next/navigation";

// Old clinician URL; the screening screen now lives at "/".
export default async function LegacyScreeningPage({ searchParams }: { searchParams: Promise<{ intake?: string }> }) {
  const { intake } = await searchParams;
  redirect(intake ? `/?intake=${encodeURIComponent(intake)}` : "/");
}

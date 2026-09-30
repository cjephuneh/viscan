import type { Metadata } from "next";
import { ScreeningScreen } from "@/components/screening-screen";

export const metadata: Metadata = { title: "Screening · VISCAN" };

export default async function ScreeningPage({ searchParams }: { searchParams: Promise<{ intake?: string }> }) {
  const { intake } = await searchParams;
  return <ScreeningScreen intakeId={intake} />;
}

import type { Metadata } from "next";
import { ScreeningScreen } from "@/components/screening-screen";

export const metadata: Metadata = { title: "Screening · VISCAN" };

// The app opens straight on the clinician screen: patient details + VIA image.
export default async function ScreeningPage({ searchParams }: { searchParams: Promise<{ intake?: string }> }) {
  const { intake } = await searchParams;
  return <ScreeningScreen intakeId={intake} />;
}

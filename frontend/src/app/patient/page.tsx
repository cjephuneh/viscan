import type { Metadata } from "next";
import { WelcomeScreen } from "@/components/welcome-screen";

export const metadata: Metadata = { title: "Patient check-in · VISCAN" };

// Patient-facing screen (no staff navigation): Mia guides the check-in.
export default function PatientPage() {
  return <WelcomeScreen />;
}

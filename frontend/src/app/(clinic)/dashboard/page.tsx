import type { Metadata } from "next";
import { DashboardScreen } from "@/components/dashboard-screen";

export const metadata: Metadata = { title: "Overview · VISCAN" };

export default function DashboardPage() {
  return <DashboardScreen />;
}

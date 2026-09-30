import type { Metadata } from "next";
import { ScreeningsScreen } from "@/components/screenings-screen";

export const metadata: Metadata = { title: "Past screenings · VISCAN" };

export default function ScreeningsPage() {
  return <ScreeningsScreen />;
}

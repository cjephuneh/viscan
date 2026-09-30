import { notFound } from "next/navigation";
import { CareScreen } from "@/components/care-screen";

export const metadata = { title: "Referral & nearby care · VISCAN" };

export default async function CarePage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  const interpretationId = Number(id);
  if (!Number.isInteger(interpretationId) || interpretationId <= 0) notFound();
  return <CareScreen interpretationId={interpretationId} />;
}

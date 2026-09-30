import { ClinicNav } from "@/components/clinic-nav";

export default function ClinicLayout({ children }: { children: React.ReactNode }) {
  return (
    <>
      <ClinicNav />
      {children}
    </>
  );
}

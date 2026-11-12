import { ClinicFooter, ClinicNav } from "@/components/clinic-nav";

export default function ClinicLayout({ children }: { children: React.ReactNode }) {
  return (
    <div className="clinic-shell">
      <ClinicNav />
      <div className="clinic-body">
        <div className="clinic-main">{children}</div>
        <ClinicFooter />
      </div>
    </div>
  );
}

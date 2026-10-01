import { redirect } from "next/navigation";

// Clinic home is the overview dashboard.
export default function ClinicHomePage() {
  redirect("/dashboard");
}

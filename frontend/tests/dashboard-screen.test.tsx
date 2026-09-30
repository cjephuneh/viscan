import { render, screen, within } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { ClinicNav } from "@/components/clinic-nav";
import { DashboardScreen } from "@/components/dashboard-screen";

const nav = vi.hoisted(() => ({ pathname: "/dashboard", push: vi.fn() }));

vi.mock("next/navigation", () => ({
  usePathname: () => nav.pathname,
  useRouter: () => ({ push: nav.push }),
}));

const summary = {
  total: 12,
  suspicious: 4,
  not_suspicious: 7,
  indeterminate: 1,
  pending_review: 3,
  reviewed: 8,
  disputed: 1,
  referred: 2,
  follow_up_overdue: 0,
  agreement_rate: 0.75,
  last_screening_at: null,
};

const row = {
  interpretation_id: 9,
  created_at: "2026-09-30T10:00:00",
  patient_external_id: "PT-0009",
  patient_name: null,
  screening_verdict: "SUSPICIOUS",
  final_via_result: "VIA_POSITIVE",
  risk_score: 81,
  follow_up_due: null,
};

beforeEach(() => {
  vi.stubGlobal(
    "fetch",
    vi.fn(async (url: string) => {
      if (url.startsWith("/api/v1/intake")) return new Response(JSON.stringify([]));
      const overdue = url.includes("overdue=1");
      return new Response(
        JSON.stringify({ items: overdue ? [] : [row], total: overdue ? 0 : 1, page: 1, per_page: 5, pages: 1, summary }),
      );
    }),
  );
});

afterEach(() => {
  vi.unstubAllGlobals();
  nav.pathname = "/dashboard";
});

describe("ClinicNav", () => {
  it("marks the current section, including care pages under past screenings", () => {
    nav.pathname = "/care/9";
    render(<ClinicNav />);
    const links = within(screen.getByRole("navigation", { name: "Clinic" }));
    expect(links.getByRole("link", { name: "Past screenings" })).toHaveAttribute("aria-current", "page");
    expect(links.getByRole("link", { name: "Overview" })).not.toHaveAttribute("aria-current");
    expect(screen.getByRole("link", { name: "Patient check-in" })).toHaveAttribute("href", "/");
  });
});

describe("DashboardScreen", () => {
  it("shows totals, quick actions and work queues", async () => {
    render(<DashboardScreen />);
    expect(screen.getByRole("heading", { level: 1, name: "Overview" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /Start a screening/ })).toHaveAttribute("href", "/screening");
    expect(await screen.findByText("75%")).toBeInTheDocument();

    const review = screen.getByRole("region", { name: /Needs your review/ });
    expect(await within(review).findByText("PT-0009")).toBeInTheDocument();
    expect(within(review).getByRole("link", { name: "See all →" })).toHaveAttribute(
      "href",
      "/screenings?status=pending&sort=risk",
    );
    expect(await screen.findByText("No overdue follow-ups.")).toBeInTheDocument();
    expect(screen.getByRole("region", { name: "Checked in and waiting" })).toBeInTheDocument();
  });
});

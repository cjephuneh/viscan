import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { ScreeningsScreen } from "@/components/screenings-screen";
import type { ScreeningPage, ScreeningRow } from "@/lib/history";

function row(overrides: Partial<ScreeningRow> = {}): ScreeningRow {
  const id = overrides.interpretation_id ?? 7;
  return {
    interpretation_id: id,
    created_at: "2026-09-29T10:15:00+00:00",
    patient_external_id: "PT-0042",
    patient_name: "Aline Uwase",
    intake_id: 3,
    age: 38,
    hiv_status: "positive",
    symptoms: [],
    site: "Kigali HC",
    screening_verdict: "SUSPICIOUS",
    via_result: "VIA_POSITIVE",
    final_via_result: "VIA_POSITIVE",
    final_is_suspicious: true,
    result_source: "clinician",
    confirmed_by: "nurse-07",
    agrees_with_ai: true,
    clinician_notes: "Dense lesion at 3 o'clock",
    risk_score: 72,
    suspicion_level: "HIGH",
    swede_score: 6,
    confidence: 0.84,
    lesion_count: 2,
    urgency: "urgent",
    action: "Offer thermal ablation today.",
    follow_up_due: "2026-09-01",
    follow_up_overdue: true,
    review_status: "reviewed",
    referral: { hospital: "CHUK", status: "sent", urgency: "urgent" },
    notifications: 1,
    coach_sessions: 0,
    links: {
      self: `/api/v1/interpretations/${id}`,
      thumbnail: `/api/v1/images/${id}/thumb.jpg`,
      image: `/api/v1/images/${id}/file`,
      overlay: `/api/v1/interpretations/${id}/overlay.png`,
      report: `/api/v1/interpretations/${id}/report`,
    },
    ...overrides,
  };
}

function page(items: ScreeningRow[], extra: Partial<ScreeningPage> = {}): ScreeningPage {
  return {
    items,
    total: items.length,
    page: 1,
    per_page: 15,
    pages: 1,
    summary: {
      total: 12,
      suspicious: 4,
      not_suspicious: 7,
      indeterminate: 1,
      pending_review: 3,
      reviewed: 8,
      disputed: 1,
      referred: 2,
      follow_up_overdue: 1,
      agreement_rate: 0.9,
      last_screening_at: null,
    },
    ...extra,
  };
}

const fetchMock = vi.fn();

beforeEach(() => {
  fetchMock.mockImplementation(async () =>
    new Response(JSON.stringify(page([row(), row({ interpretation_id: 5, screening_verdict: "NOT_SUSPICIOUS", patient_name: null, referral: null, follow_up_overdue: false })]))),
  );
  vi.stubGlobal("fetch", fetchMock);
});

afterEach(() => {
  vi.unstubAllGlobals();
  fetchMock.mockReset();
});

const lastUrl = () => String(fetchMock.mock.calls.at(-1)?.[0]);

describe("ScreeningsScreen", () => {
  it("lists past screenings with totals and badges", async () => {
    render(<ScreeningsScreen />);
    expect(await screen.findByText("Aline Uwase")).toBeInTheDocument();
    expect(screen.getByRole("heading", { level: 1, name: "Past screenings" })).toBeInTheDocument();
    expect(screen.getByText("2 screenings")).toBeInTheDocument();
    expect(screen.getByText("90%")).toBeInTheDocument();
    expect(screen.getByText("Referred", { selector: ".badge" })).toBeInTheDocument();
    expect(screen.getByText("Follow-up overdue", { selector: ".badge" })).toBeInTheDocument();
    expect(screen.getAllByText("by nurse-07")).toHaveLength(2);
    expect(lastUrl()).toBe("/api/v1/screenings?sort=newest&page=1&per_page=15");
  });

  it("filters by verdict and search", async () => {
    render(<ScreeningsScreen />);
    await screen.findByText("Aline Uwase");

    fireEvent.click(screen.getByRole("button", { name: "Suspicious" }));
    await waitFor(() => expect(lastUrl()).toContain("verdict=SUSPICIOUS"));

    fireEvent.change(screen.getByRole("searchbox"), { target: { value: "PT-0042" } });
    await waitFor(() => expect(lastUrl()).toContain("q=PT-0042"));
    expect(lastUrl()).toContain("verdict=SUSPICIOUS");
  });

  it("expands a row with actions", async () => {
    render(<ScreeningsScreen />);
    await screen.findByText("Aline Uwase");
    fireEvent.click(screen.getByRole("button", { name: "Show details for reading 7" }));
    expect(screen.getByText("Offer thermal ablation today.")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Learn with Kezia" })).toHaveAttribute("href", "/learn?case=7");
    expect(screen.getByRole("link", { name: "Care & referral" })).toHaveAttribute("href", "/care/7");
  });

  it("shows an empty state", async () => {
    fetchMock.mockImplementation(async () => new Response(JSON.stringify(page([]))));
    render(<ScreeningsScreen />);
    expect(await screen.findByText(/No screenings yet/)).toBeInTheDocument();
  });
});

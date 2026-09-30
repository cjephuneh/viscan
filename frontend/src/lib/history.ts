import type { ViaResult, Verdict } from "@/lib/viscan";

export type ScreeningRow = {
  interpretation_id: number;
  created_at: string | null;
  patient_external_id: string | null;
  patient_name: string | null;
  intake_id: number | null;
  age: number | null;
  hiv_status: string | null;
  symptoms: string[];
  site: string | null;
  screening_verdict: Verdict;
  via_result: ViaResult;
  final_via_result: ViaResult;
  final_is_suspicious: boolean;
  result_source: "clinician" | "ai";
  confirmed_by: string | null;
  agrees_with_ai: boolean | null;
  clinician_notes: string | null;
  risk_score: number | null;
  suspicion_level: string | null;
  swede_score: number | null;
  confidence: number | null;
  lesion_count: number;
  urgency: string | null;
  action: string | null;
  follow_up_due: string | null;
  follow_up_overdue: boolean;
  review_status: "pending" | "reviewed" | "disputed";
  referral: { hospital: string | null; status: string; urgency: string | null } | null;
  notifications: number;
  coach_sessions: number;
  links: { self: string; thumbnail: string; image: string; overlay: string; report: string };
};

export type ScreeningSummary = {
  total: number;
  suspicious: number;
  not_suspicious: number;
  indeterminate: number;
  pending_review: number;
  reviewed: number;
  disputed: number;
  referred: number;
  follow_up_overdue: number;
  agreement_rate: number | null;
  last_screening_at: string | null;
};

export type ScreeningPage = {
  items: ScreeningRow[];
  total: number;
  page: number;
  per_page: number;
  pages: number;
  summary: ScreeningSummary;
};

export type ScreeningQuery = {
  q?: string;
  verdict?: Verdict | "";
  status?: ScreeningRow["review_status"] | "";
  from?: string;
  to?: string;
  sort?: "newest" | "oldest" | "risk";
  referred?: boolean;
  overdue?: boolean;
  page?: number;
  per_page?: number;
};

export async function listScreenings(query: ScreeningQuery = {}): Promise<ScreeningPage> {
  const params = new URLSearchParams();
  for (const [key, value] of Object.entries(query)) {
    if (value === undefined || value === "" || value === false) continue;
    params.set(key, value === true ? "1" : String(value));
  }
  let res: Response;
  try {
    res = await fetch(`/api/v1/screenings${params.size ? `?${params}` : ""}`);
  } catch {
    throw new Error("Could not reach VIScan. Check the connection and try again.");
  }
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(data.error || `Request failed (${res.status})`);
  return data as ScreeningPage;
}

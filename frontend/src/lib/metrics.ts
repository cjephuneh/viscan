export type ClinicMetrics = {
  total_interpretations: number;
  by_engine: Record<string, number>;
  by_verdict: Record<string, number>;
  by_via_result: Record<string, number>;
  by_review_status: Record<string, number>;
  average_risk_score: number | null;
  average_latency_ms: number | null;
  clinician_agreement: {
    reviewed: number;
    agreement_rate: number | null;
    cohens_kappa: number | null;
    confusion_matrix_ai_vs_clinician: Record<string, Record<string, number>>;
  };
  vs_histology_cin2_plus: {
    cases_with_reference: number;
    true_positive: number;
    false_positive: number;
    true_negative: number;
    false_negative: number;
    sensitivity: number | null;
    specificity: number | null;
    ppv: number | null;
    npv: number | null;
  };
};

function isClinicMetrics(data: unknown): data is ClinicMetrics {
  if (!data || typeof data !== "object") return false;
  const row = data as Record<string, unknown>;
  return "clinician_agreement" in row && "by_review_status" in row && "total_interpretations" in row;
}

export async function fetchClinicMetrics(): Promise<ClinicMetrics> {
  let res: Response;
  try {
    res = await fetch("/api/v1/metrics");
  } catch {
    throw new Error("Could not reach VIScan. Check the connection and try again.");
  }
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error((data as { error?: string }).error || `Request failed (${res.status})`);
  if (!isClinicMetrics(data)) throw new Error("Performance metrics response was incomplete.");
  return data;
}

export function isoDaysAgo(days: number): string {
  const date = new Date();
  date.setHours(0, 0, 0, 0);
  date.setDate(date.getDate() - days);
  return date.toISOString().slice(0, 10);
}

export function formatLatency(ms: number | null | undefined): string {
  if (ms == null || Number.isNaN(ms)) return "—";
  if (ms < 1000) return `${Math.round(ms)} ms`;
  return `${(ms / 1000).toFixed(ms >= 10000 ? 0 : 1)} s`;
}

export function formatPercent(rate: number | null | undefined): string {
  if (rate == null || Number.isNaN(rate)) return "—";
  return `${Math.round(rate * 100)}%`;
}

export function formatRate(rate: number | null | undefined): number | null {
  if (rate == null || Number.isNaN(rate)) return null;
  return Math.max(0, Math.min(100, Math.round(rate * 100)));
}

export type Verdict = "SUSPICIOUS" | "NOT_SUSPICIOUS" | "INDETERMINATE";
export type ViaResult = "VIA_NEGATIVE" | "VIA_POSITIVE" | "SUSPICIOUS_FOR_CANCER" | "INADEQUATE";
export type Channel = "sms" | "whatsapp";

export type Lesion = {
  id: number;
  clock_start: number;
  clock_end: number;
  area_percent: number;
  density: string;
  margins: string;
  surface: string;
  vessel_pattern: string;
  touches_scj: boolean;
  extends_into_canal: boolean;
  description: string;
};

export type ChecklistItem = { criterion: string; met: boolean | null; detail: string };

export type Interpretation = {
  interpretation_id: number;
  image_id: number;
  patient_id: number | null;
  verdict: {
    screening_verdict: Verdict;
    is_suspicious: boolean;
    label: string;
    suspicion_level: string;
    risk_score: number | null;
    via_result: ViaResult;
    confidence: number;
  };
  diagnosis: { via_result: ViaResult; confidence: number; summary: string; urgency: string };
  clinical_summary: {
    key_observations: string[];
    rationale: string;
    patient_explanation: string;
    counselling_points: string[];
    clinician_checklist: string[];
  };
  image_assessment: {
    image_modality: string;
    transformation_zone_type: string;
    scj_visibility: string;
    adequacy: { adequate: boolean; issues: string[] };
  };
  findings: {
    acetowhite_density?: string;
    lesion_margins?: string;
    lesion_clock_positions?: number[];
    cervix_area_involved_percent?: number;
    extends_into_canal?: boolean;
  };
  lesions: Lesion[];
  swede: { total: number; max: number; interpretation: string };
  histology_likelihood: Record<string, number> | null;
  treatment_eligibility: { ablation_eligible: boolean | null; checklist: ChecklistItem[] };
  recommendation: {
    action: string;
    urgency: string;
    ablation_eligible: boolean | null;
    follow_up_months: number | null;
    reasons: string[];
    flags: string[];
  };
  follow_up_due: string | null;
  history: {
    trend: string;
    previous_screens?: PriorScreen[];
    days_since_last_screen?: number | null;
  };
  review_status: string;
  engine: { name: string; model: string; latency_ms: number };
  /** Pre-acetic-acid frame stored with the visit, if the clinician added one. */
  before_image_id?: number | null;
  links: {
    self: string;
    image: string;
    image_before?: string | null;
    overlay: string;
    report: string;
    annotate: string;
    /** ai-avatar video report (created after clinician confirmation). */
    video_status?: string;
    video_player?: string;
  };
  disclaimer: string;
};

export type VideoStatus = "pending" | "running" | "completed" | "failed" | "uninitiated";

export type VideoReport = {
  report_id: string;
  scan_id: string;
  video_id: string | null;
  status: VideoStatus;
  video_url: string | null;
  player_url: string | null;
  /** Written narration available as soon as the report is created. */
  generated_script?: string | null;
  duration_seconds: number | null;
  expires_at: string | null;
};

export type Supply = { item: string; why: string; prescription: boolean };

export type PartnerHospital = {
  id: number;
  name: string;
  address: string | null;
  phone: string | null;
  whatsapp: string | null;
  latitude: number;
  longitude: number;
  services: string[];
  opening_hours: string | null;
  is_demo: boolean;
  distance_km: number;
};

export type Pharmacy = {
  id: string;
  name: string;
  latitude: number;
  longitude: number;
  distance_km: number;
  address: string | null;
  phone: string | null;
  opening_hours: string | null;
  osm_url: string;
};

export type Referral = {
  id: number;
  hospital: PartnerHospital;
  urgency: string | null;
  status: string;
  created_at: string;
};

export type NotificationRecord = {
  id: number;
  channel: Channel;
  recipient: string;
  message: string;
  status: string;
  created_at: string;
};

export type CareSummary = {
  interpretation_id: number;
  patient_external_id: string | null;
  final_via_result: ViaResult;
  result_source: "ai" | "clinician";
  is_suspicious: boolean;
  needs_referral: boolean;
  urgency: string | null;
  action: string | null;
  suggested_supplies: Supply[];
  referrals: Referral[];
  notifications: NotificationRecord[];
  message_preview: Record<Channel, string>;
};

export type VisitDetails = {
  patientId: string;
  age: string;
  hivStatus: string;
  hpvStatus: string;
  pregnant: string;
  previouslyTreated: string;
  smoker: string;
  parity: string;
  symptoms: string[];
  site: string;
  clinicianId: string;
};

export type PriorScreen = {
  interpretation_id: number;
  date: string | null;
  via_result: ViaResult;
  source: "clinician" | "ai";
  screening_verdict?: Verdict | null;
  risk_score?: number | null;
  review_status?: string | null;
  site?: string | null;
};

export type PatientLookup = {
  found: boolean;
  external_id: string;
  id?: number;
  age?: number | null;
  hiv_status?: string | null;
  screenings_count: number;
  previous_screens: PriorScreen[];
  last_visit: {
    age_at_visit?: number | null;
    hiv_status?: string | null;
    hpv_status?: string | null;
    pregnant?: boolean | null;
    previously_treated?: boolean | null;
    smoker?: boolean | null;
    parity?: number | null;
    symptoms?: string[];
    site?: string | null;
  } | null;
  prefill: {
    patient_external_id: string;
    age: number | null;
    hiv_status: string;
    hpv_status: string;
    pregnant: boolean | null;
    previously_treated: boolean | null;
    smoker: boolean | null;
    parity: number | null;
    symptoms: string[];
    site: string | null;
    previous_screening_result: ViaResult | null;
  } | null;
};

const API = "/api/v1";

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let res: Response;
  try {
    res = await fetch(`${API}${path}`, init);
  } catch {
    throw new Error("Could not reach VIScan. Check the connection and try again.");
  }
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(data.error || `Request failed (${res.status})`);
  return data as T;
}

function postJson<T>(path: string, body: unknown): Promise<T> {
  return request<T>(path, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
}

export function interpretImage(
  file: File,
  visit: VisitDetails,
  intakeId?: number,
  /** Optional pre-acetic-acid view of the same cervix (baseline for the model). */
  beforeFile?: File | null,
): Promise<Interpretation> {
  const form = new FormData();
  form.append("image", file);
  if (beforeFile) form.append("image_before", beforeFile);
  if (intakeId) form.append("intake_id", String(intakeId));
  const fields: Record<string, string> = {
    patient_external_id: visit.patientId.trim(),
    age: visit.age,
    hiv_status: visit.hivStatus,
    hpv_status: visit.hpvStatus,
    pregnant: visit.pregnant,
    previously_treated: visit.previouslyTreated,
    smoker: visit.smoker,
    parity: visit.parity,
    site: visit.site,
    clinician_id: visit.clinicianId,
  };
  for (const [key, value] of Object.entries(fields)) if (value.trim()) form.append(key, value.trim());
  for (const symptom of visit.symptoms) form.append("symptoms", symptom);
  return request<Interpretation>("/interpret", { method: "POST", body: form });
}

export const confirmReading = (id: number, body: { clinician_id: string; via_result: ViaResult; notes?: string }) =>
  postJson<{ agrees_with_ai: boolean; review_status: string }>(`/interpretations/${id}/annotations`, body);

export const getInterpretation = (id: number) => request<Interpretation>(`/interpretations/${id}`);
export const getCare = (id: number) => request<CareSummary>(`/interpretations/${id}/care`);

/** Load a returning patient's stored demographics and prior VIA readings by clinic ID. */
export function lookupPatient(externalId: string): Promise<PatientLookup> {
  const id = externalId.trim();
  if (!id) {
    return Promise.resolve({
      found: false,
      external_id: "",
      screenings_count: 0,
      previous_screens: [],
      last_visit: null,
      prefill: null,
    });
  }
  return request<PatientLookup>(`/patients/lookup?external_id=${encodeURIComponent(id)}`);
}

export function trendLabel(trend: string | undefined): string {
  switch (trend) {
    case "first_screen_on_record":
      return "First screen on record";
    case "new_positive":
      return "New positive since last screen";
    case "persistent_positive":
      return "Persistent positive";
    case "resolved_since_last_screen":
      return "Resolved since last screen";
    case "stable_negative":
      return "Stable negative";
    case "not_comparable":
      return "Not comparable with last screen";
    default:
      return humanize(trend);
  }
}

export const getPartnerHospitals = (lat?: number, lng?: number) =>
  request<{ center: { lat: number; lng: number }; results: PartnerHospital[] }>(
    lat === undefined || lng === undefined ? "/partner-hospitals" : `/partner-hospitals?lat=${lat}&lng=${lng}`,
  );

export const getPharmacies = (lat: number, lng: number, radius: number) =>
  request<{ results: Pharmacy[] }>(`/places/pharmacies?lat=${lat}&lng=${lng}&radius=${radius}`);

export const referPatient = (id: number, hospitalId: number, referredBy?: string) =>
  postJson<Referral>(`/interpretations/${id}/referrals`, { hospital_id: hospitalId, referred_by: referredBy });

export const sendResults = (id: number, body: { channel: Channel; phone: string; message?: string; sent_by?: string }) =>
  postJson<NotificationRecord>(`/interpretations/${id}/notifications`, body);

export function verdictTone(verdict: Verdict | undefined): "alert" | "clear" | "neutral" {
  if (verdict === "SUSPICIOUS") return "alert";
  if (verdict === "NOT_SUSPICIOUS") return "clear";
  return "neutral";
}

export function verdictLabel(verdict: Verdict | undefined): string {
  if (verdict === "SUSPICIOUS") return "Suspicious";
  if (verdict === "NOT_SUSPICIOUS") return "Not suspicious";
  return "Cannot assess";
}

export function viaToVerdict(via: ViaResult): Verdict {
  if (via === "VIA_POSITIVE" || via === "SUSPICIOUS_FOR_CANCER") return "SUSPICIOUS";
  if (via === "VIA_NEGATIVE") return "NOT_SUSPICIOUS";
  return "INDETERMINATE";
}

export const humanize = (value: string | null | undefined) =>
  value ? value.replaceAll("_", " ").replace(/^\w/, (c) => c.toUpperCase()) : "—";

/** Deterministic id the interpreter uses when it asks ai-avatar for the video report. */
export function videoScanId(interpretationId: number): string {
  return `viscan-${interpretationId}`;
}

export function videoPlayerUrl(interpretationId: number): string {
  return `/player/${videoScanId(interpretationId)}`;
}

/**
 * Video report status from ai-avatar. Returns `null` while the report does not
 * exist yet (the interpreter creates it right after the clinician confirms).
 */
export async function getVideoReport(interpretationId: number): Promise<VideoReport | null> {
  const res = await fetch(`${API}/reports/${videoScanId(interpretationId)}/video`, { cache: "no-store" });
  if (res.status === 404) return null;
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(data.error || data.detail || `Request failed (${res.status})`);
  return data as VideoReport;
}

export type VideoSession = {
  report_id: string;
  session_token: string;
  persona_id: string | null;
  generated_script: string;
  expires_in_seconds: number;
};

/**
 * Live (WebRTC) session in which the avatar presents the confirmed report
 * immediately, while the MP4 is still rendering. `null` if the report does
 * not exist yet.
 */
export async function getVideoSession(interpretationId: number): Promise<VideoSession | null> {
  const res = await fetch(`${API}/reports/${videoScanId(interpretationId)}/session`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: "{}",
    cache: "no-store",
  });
  if (res.status === 404) return null;
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(data.error || data.detail || `Request failed (${res.status})`);
  return data as VideoSession;
}

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
  history: { trend: string };
  review_status: string;
  engine: { name: string; model: string; latency_ms: number };
  links: { self: string; image: string; overlay: string; report: string; annotate: string };
  disclaimer: string;
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

export function interpretImage(file: File, visit: VisitDetails): Promise<Interpretation> {
  const form = new FormData();
  form.append("image", file);
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

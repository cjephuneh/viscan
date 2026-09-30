import { vi } from "vitest";
import type { Intake } from "@/lib/intake";
import type { CareSummary, Interpretation, PartnerHospital, Pharmacy } from "@/lib/viscan";

export const interpretationFixture: Interpretation = {
  interpretation_id: 7,
  image_id: 3,
  patient_id: 1,
  verdict: {
    screening_verdict: "SUSPICIOUS",
    is_suspicious: true,
    label: "Suspicious",
    suspicion_level: "high",
    risk_score: 72,
    via_result: "VIA_POSITIVE",
    confidence: 0.84,
  },
  diagnosis: {
    via_result: "VIA_POSITIVE",
    confidence: 0.84,
    summary: "Offer thermal ablation today (screen-and-treat).",
    urgency: "soon",
  },
  clinical_summary: {
    key_observations: ["Dense acetowhite area at 3-5 o'clock touching the SCJ"],
    rationale: "Well-defined acetowhite lesion.",
    patient_explanation: "An area needs treatment.",
    counselling_points: [],
    clinician_checklist: [],
  },
  image_assessment: {
    image_modality: "via_white_light",
    transformation_zone_type: "type_1",
    scj_visibility: "fully_visible",
    adequacy: { adequate: true, issues: [] },
  },
  findings: {
    acetowhite_density: "dense",
    lesion_margins: "sharp",
    lesion_clock_positions: [3, 4, 5],
    cervix_area_involved_percent: 25,
    extends_into_canal: false,
  },
  lesions: [
    {
      id: 1,
      clock_start: 3,
      clock_end: 5,
      area_percent: 25,
      density: "dense",
      margins: "sharp",
      surface: "smooth",
      vessel_pattern: "none",
      touches_scj: true,
      extends_into_canal: false,
      description: "",
    },
  ],
  swede: { total: 4, max: 8, interpretation: "intermediate" },
  histology_likelihood: { normal: 0.1, cin1: 0.3, cin2_plus: 0.55, invasive_cancer: 0.05 },
  treatment_eligibility: {
    ablation_eligible: true,
    checklist: [{ criterion: "No suspicion of invasive cancer", met: true, detail: "" }],
  },
  recommendation: {
    action: "Offer thermal ablation today (screen-and-treat).",
    urgency: "soon",
    ablation_eligible: true,
    follow_up_months: 12,
    reasons: [],
    flags: ["Contact bleeding noted"],
  },
  follow_up_due: "2027-09-30",
  history: { trend: "first_screen_on_record" },
  review_status: "pending",
  engine: { name: "openai", model: "gpt-5", latency_ms: 42000 },
  links: {
    self: "/api/v1/interpretations/7",
    image: "/api/v1/images/3/file",
    overlay: "/api/v1/interpretations/7/overlay.png",
    report: "/api/v1/interpretations/7/report",
    annotate: "/api/v1/interpretations/7/annotations",
  },
  disclaimer: "Decision support only.",
};

export const hospitalFixture: PartnerHospital = {
  id: 11,
  name: "Women's Health Centre (demo)",
  address: "Demo address",
  phone: "+000 000 000 002",
  whatsapp: null,
  latitude: -1.96,
  longitude: 30.08,
  services: ["colposcopy", "LEEP"],
  opening_hours: "Mon-Sat",
  is_demo: true,
  distance_km: 2.9,
};

export const pharmacyFixture: Pharmacy = {
  id: "node/1",
  name: "Pharmacie Conseil",
  latitude: -1.945,
  longitude: 30.062,
  distance_km: 0.3,
  address: "KN 4 Ave",
  phone: null,
  opening_hours: null,
  osm_url: "https://www.openstreetmap.org/node/1",
};

export function careFixture(referred = false): CareSummary {
  return {
    interpretation_id: 7,
    patient_external_id: "PT-1",
    final_via_result: "VIA_POSITIVE",
    result_source: "clinician",
    is_suspicious: true,
    needs_referral: false,
    urgency: "soon",
    action: "Offer thermal ablation today (screen-and-treat).",
    suggested_supplies: [{ item: "Sanitary pads", why: "Discharge after treatment", prescription: false }],
    referrals: referred
      ? [{ id: 1, hospital: hospitalFixture, urgency: "soon", status: "sent", created_at: "2026-09-30T10:00:00" }]
      : [],
    notifications: [],
    message_preview: { sms: "SMS preview", whatsapp: "WhatsApp preview" },
  };
}

const json = (body: unknown, status = 200) =>
  new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } });

export const intakeFixture: Intake = {
  id: 5,
  code: "K7M3Q",
  status: "completed",
  channel: "avatar",
  full_name: "Grace Uwase",
  preferred_name: "Grace",
  age: 38,
  sex: "female",
  language: "en",
  answers: {
    pregnant: { value: false, said: "no", at: "" },
    hiv_status: { value: "positive", said: "positive", at: "" },
    symptoms: { value: ["postcoital_bleeding"], said: "bleeding after sex", at: "" },
  },
  feelings: [
    { level: 5, note: "scared", at: "" },
    { level: 2, note: "", at: "" },
  ],
  anxiety: { start: 5, end: 2, change: -3 },
  concerns: [{ concern: "Worried it will hurt", category: "pain", at: "" }],
  patient_questions: [],
  topics_covered: ["what_is_via", "what_to_expect"],
  breathing_exercises: 1,
  summary: "Grace was nervous about pain and calmer after breathing.",
  patient_id: null,
  visit_id: null,
  interpretation_id: null,
  created_at: "",
  completed_at: new Date().toISOString(),
  prefill: {
    patient_external_id: "INT-K7M3Q",
    age: 38,
    hiv_status: "positive",
    pregnant: false,
    previously_treated: null,
    previous_screening_result: null,
    parity: 3,
    smoker: false,
    contraception: null,
    symptoms: ["postcoital_bleeding"],
    phone: "+250788111222",
    result_channel: "whatsapp",
  },
  flags: [{ level: "alert", text: "Reports postcoital bleeding." }],
};

export function mockFetch(overrides: { pharmaciesStatus?: number; interpretError?: string; waiting?: Intake[] } = {}) {
  let referred = false;
  const fn = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
    const url = String(input);
    const method = init?.method ?? "GET";
    if (url === "/api/v1/interpret")
      return overrides.interpretError ? json({ error: overrides.interpretError }, 502) : json(interpretationFixture, 201);
    if (url.startsWith("/api/v1/intake?")) return json(overrides.waiting ?? []);
    if (url === `/api/v1/intake/${intakeFixture.id}` || url === `/api/v1/intake/code/${intakeFixture.code}`)
      return json(intakeFixture);
    if (url.endsWith("/annotations")) return json({ agrees_with_ai: true, review_status: "reviewed" }, 201);
    if (url.endsWith("/care")) return json(careFixture(referred));
    if (url.endsWith("/notifications") && method === "POST") {
      const body = JSON.parse(String(init?.body));
      return json(
        { id: 1, channel: body.channel, recipient: body.phone, message: body.message, status: "simulated", created_at: "" },
        201,
      );
    }
    if (url.endsWith("/referrals") && method === "POST") {
      referred = true;
      return json(careFixture(true).referrals[0], 201);
    }
    if (url.startsWith("/api/v1/partner-hospitals"))
      return json({ center: { lat: -1.9441, lng: 30.0619 }, results: [hospitalFixture] });
    if (url.startsWith("/api/v1/places/pharmacies")) {
      if (overrides.pharmaciesStatus) return json({ error: "Pharmacy search is unavailable.", results: [] }, overrides.pharmaciesStatus);
      return json({ results: [pharmacyFixture] });
    }
    return json({ error: "not found" }, 404);
  });
  vi.stubGlobal("fetch", fn);
  return fn;
}

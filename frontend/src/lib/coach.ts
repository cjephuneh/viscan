import type { AvatarToken } from "@/lib/intake";

export type CoachEventType =
  | "highlight"
  | "card"
  | "lesion"
  | "quiz_asked"
  | "quiz_answer"
  | "action_step"
  | "action_done"
  | "learning"
  | "roleplay_start"
  | "roleplay_end"
  | "finish"
  | "transcript";

export type QuizItem = {
  question: string;
  options: string[];
  correct_index: number;
  explanation: string;
  chosen_index: number | null;
  correct: boolean | null;
};

export type ActionStep = { step: string; why: string; done: boolean };
export type Roleplay = { scenario: string; strengths: string[]; improve: string | null };

export type CoachSession = {
  id: number;
  interpretation_id: number | null;
  clinician_id: string | null;
  status: "active" | "completed";
  topics: { topic: string; summary: string }[];
  quiz: QuizItem[];
  score: { asked: number; answered: number; correct: number };
  action_plan: ActionStep[];
  roleplays: Roleplay[];
  summary: string | null;
  created_at: string;
  ended_at: string | null;
};

export type WorklistItem = {
  interpretation_id: number;
  patient_external_id: string | null;
  created_at: string;
  screening_verdict: "SUSPICIOUS" | "NOT_SUSPICIOUS" | "INDETERMINATE";
  via_result: string;
  risk_score: number | null;
  action: string | null;
  review_status: string;
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

const postJson = <T>(path: string, body: unknown) =>
  request<T>(path, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });

export const getCoachPersona = () =>
  request<{ available: boolean; name: string; image_url: string | null }>("/coach/persona");

export const startCoachSession = (interpretationId: number | null, clinicianId?: string) =>
  postJson<CoachSession>("/coach/sessions", {
    interpretation_id: interpretationId ?? undefined,
    clinician_id: clinicianId || undefined,
  });

export const getCoachToken = (id: number) => postJson<AvatarToken>(`/coach/sessions/${id}/token`, {});

export const sendCoachEvent = (id: number, type: CoachEventType, data: object, anamSessionId?: string | null) =>
  postJson<{ message: string; session: CoachSession }>(`/coach/sessions/${id}/events`, {
    type,
    data,
    anam_session_id: anamSessionId ?? undefined,
  });

export const listCoachSessions = (clinicianId?: string) =>
  request<CoachSession[]>(`/coach/sessions?limit=20${clinicianId ? `&clinician_id=${encodeURIComponent(clinicianId)}` : ""}`);

export const getWorklist = () => request<WorklistItem[]>("/worklist?status=all&limit=30");

export const TEACHING_CARDS: Record<string, { title: string; points: string[]; art: string }> = {
  acetowhite_change: {
    title: "Acetowhite change",
    art: "cervix",
    points: [
      "Acetic acid makes abnormal cells turn white for about a minute.",
      "Positive: dense, opaque, well-defined white touching the SCJ.",
      "Negative: faint, translucent or patchy whiteness, or white far from the SCJ.",
    ],
  },
  transformation_zone: {
    title: "Transformation zone",
    art: "zones",
    points: [
      "The area where precancer starts, between the original and current SCJ.",
      "Type 1 and 2: fully visible, so ablation is possible.",
      "Type 3: goes into the canal and can't be fully seen, so refer for LEEP.",
    ],
  },
  squamocolumnar_junction: {
    title: "Squamocolumnar junction",
    art: "zones",
    points: [
      "The line where pink squamous skin meets red columnar tissue.",
      "Lesions touching the SCJ are the ones that matter.",
      "If you can't see the whole SCJ, don't ablate.",
    ],
  },
  swede_score: {
    title: "Modified Swede score",
    art: "score",
    points: [
      "Points for acetowhiteness, margins, vessels and lesion size (0 to 8 without iodine).",
      "0-4: likely low grade. 5-6: possible high grade. 7-8: high grade likely.",
      "A teaching aid in VIScan, not a diagnosis.",
    ],
  },
  risk_index: {
    title: "VIScan risk index",
    art: "score",
    points: [
      "0-100 points built from the AI result, Swede features, red flags and risk factors.",
      "Each point is listed so you can see why the score is high.",
      "It orders the worklist; it does not replace your judgement.",
    ],
  },
  ablation_eligibility: {
    title: "Can I ablate?",
    art: "check",
    points: [
      "No suspicion of cancer.",
      "SCJ fully visible (TZ type 1 or 2) and lesion does not enter the canal.",
      "Lesion covers less than 75% of the cervix, and the patient is not pregnant.",
    ],
  },
  thermal_ablation: {
    title: "Thermal ablation",
    art: "treat",
    points: [
      "Probe at 100 °C for 20-40 seconds per application, overlapping to cover the lesion.",
      "No anaesthetic usually needed; mild cramping is normal.",
      "Avoid intercourse for 4 weeks; watery discharge for a few weeks.",
    ],
  },
  cryotherapy: {
    title: "Cryotherapy",
    art: "treat",
    points: [
      "Freeze-thaw-freeze: 3 minutes, 5 minutes thaw, 3 minutes.",
      "Probe must cover the whole lesion.",
      "Same eligibility rules as thermal ablation.",
    ],
  },
  leep_referral: {
    title: "When to refer for LEEP",
    art: "refer",
    points: [
      "Not eligible for ablation: TZ type 3, large lesion, or canal involvement.",
      "LEEP removes the zone and gives tissue for histology.",
      "Refer within weeks; make sure the patient knows where and when.",
    ],
  },
  cancer_red_flags: {
    title: "Cancer red flags",
    art: "alert",
    points: [
      "Ulcer, cauliflower-like growth, necrosis, contact bleeding, atypical vessels.",
      "Do not ablate. Refer urgently for biopsy, the same week.",
      "Counsel calmly: this needs a closer look, not a diagnosis yet.",
    ],
  },
  counselling: {
    title: "Counselling a positive result",
    art: "talk",
    points: [
      "Start with: this is common and treatable. A positive screen is not cancer.",
      "Explain the next step, what it feels like, and recovery.",
      "Check understanding: ask her to tell you back what happens next.",
    ],
  },
  follow_up_intervals: {
    title: "Follow-up intervals",
    art: "calendar",
    points: [
      "Negative: rescreen in 3 years (often 2 years if living with HIV).",
      "After treatment: review at 12 months.",
      "Suspected cancer: referral within 1 month, ideally the same week.",
    ],
  },
  hiv_and_screening: {
    title: "HIV and screening",
    art: "shield",
    points: [
      "Women living with HIV have higher risk and faster progression.",
      "Screen from age 25 and more often.",
      "Treat promptly when eligible; follow up closely.",
    ],
  },
  inadequate_image: {
    title: "Inadequate image",
    art: "camera",
    points: [
      "Re-apply acetic acid and wait a full minute.",
      "Improve light and focus; clear mucus or blood gently.",
      "Make sure the whole cervix and SCJ are in frame.",
    ],
  },
  ai_limits: {
    title: "What the AI can't do",
    art: "ai",
    points: [
      "It reads one photo; you see the patient and the whole cervix.",
      "Confidence below 75% goes to priority review.",
      "You confirm every result. If you disagree, record your finding.",
    ],
  },
};

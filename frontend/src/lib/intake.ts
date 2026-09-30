export type IntakeEventType =
  | "details"
  | "answer"
  | "feeling"
  | "concern"
  | "question"
  | "topic"
  | "breathing"
  | "finish"
  | "transcript";

export type IntakeAnswer = { value: string | number | boolean | string[] | null; said: string; at: string };
export type IntakeFlag = { level: "alert" | "warn" | "info"; text: string };

export type IntakePrefill = {
  patient_external_id: string;
  age: number | null;
  hiv_status: string;
  pregnant: boolean | null;
  previously_treated: boolean | null;
  previous_screening_result: string | null;
  parity: number | null;
  smoker: boolean | null;
  contraception: string | null;
  symptoms: string[];
  phone: string | null;
  result_channel: "sms" | "whatsapp" | "none" | null;
};

export type Intake = {
  id: number;
  code: string;
  status: "in_progress" | "completed";
  channel: "avatar" | "form";
  full_name: string | null;
  preferred_name: string | null;
  age: number | null;
  sex: string | null;
  language: string | null;
  answers: Record<string, IntakeAnswer>;
  feelings: { level: number; note: string; at: string }[];
  anxiety: { start: number | null; end: number | null; change: number | null };
  concerns: { concern: string; category: string; at: string }[];
  patient_questions: { question: string; answered: boolean; at: string }[];
  topics_covered: string[];
  breathing_exercises: number;
  summary: string | null;
  patient_id: number | null;
  visit_id: number | null;
  interpretation_id: number | null;
  created_at: string;
  completed_at: string | null;
  prefill: IntakePrefill;
  flags: IntakeFlag[];
};

export type AvatarToken = { session_token: string; persona: { name: string; image_url: string | null } };

const API = "/api/v1";

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let res: Response;
  try {
    res = await fetch(`${API}${path}`, init);
  } catch {
    throw new Error("Could not reach VIScan. Check the connection and try again.");
  }
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw Object.assign(new Error(data.error || `Request failed (${res.status})`), { status: res.status });
  return data as T;
}

const postJson = <T>(path: string, body: unknown) =>
  request<T>(path, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });

export const startIntake = (channel: "avatar" | "form" = "avatar", language = "en") =>
  postJson<Intake>("/intake", { channel, language });

export const getAvatarPersona = () =>
  request<{ available: boolean; name: string; image_url: string | null }>("/avatar/persona");

export const getAvatarToken = (id: number) => postJson<AvatarToken>(`/intake/${id}/avatar-token`, {});

export const sendIntakeEvent = (id: number, type: IntakeEventType, data: object, anamSessionId?: string | null) =>
  postJson<{ message: string; intake: Intake }>(`/intake/${id}/events`, {
    type,
    data,
    anam_session_id: anamSessionId ?? undefined,
  });

export const getIntake = (id: number | string) => request<Intake>(`/intake/${id}`);
export const getIntakeByCode = (code: string) => request<Intake>(`/intake/code/${encodeURIComponent(code.trim())}`);
export const listWaitingIntakes = () => request<Intake[]>("/intake?status=completed&unscreened=1&limit=12");

export const TOPICS: Record<string, { title: string; points: string[] }> = {
  what_is_via: {
    title: "What is VIA?",
    points: [
      "Visual Inspection with Acetic acid: a gentle look at the cervix, the opening of the womb.",
      "The nurse applies a little vinegar solution. Healthy tissue stays pink.",
      "Areas that need attention turn white for about a minute.",
    ],
  },
  why_screening_matters: {
    title: "Why it matters",
    points: [
      "It finds changes years before they could ever become cancer.",
      "Early changes are simple to treat, often the same day.",
      "Most results are normal.",
    ],
  },
  what_to_expect: {
    title: "What to expect",
    points: [
      "Undress from the waist down. You get a sheet to cover yourself.",
      "Lie back with your knees bent. The nurse gently places a speculum.",
      "Vinegar is applied and the nurse looks with a light. That's it.",
    ],
  },
  the_speculum: {
    title: "The speculum",
    points: [
      "A smooth instrument that gently holds the walls open so the nurse can see.",
      "You may feel pressure, not pain. Breathing out slowly helps.",
      "Ask the nurse to go slower or stop at any time.",
    ],
  },
  the_vinegar_test: {
    title: "The vinegar test",
    points: ["A cotton swab with diluted vinegar.", "It may feel cool or sting a little.", "No needles, no cutting."],
  },
  how_long: {
    title: "How long it takes",
    points: ["The exam itself takes about five minutes.", "The whole visit is usually under half an hour."],
  },
  results_same_day: {
    title: "Results today",
    points: ["You get your result the same day, usually right away.", "It can also be sent to you by SMS or WhatsApp."],
  },
  if_positive_treatment: {
    title: "If something is seen",
    points: [
      "A positive result does not mean cancer.",
      "White areas can often be treated the same day with a quick heat or cold treatment.",
      "Or you are referred to a partner hospital for a closer look.",
    ],
  },
  privacy: {
    title: "Your privacy",
    points: ["Only the nurse is in the room.", "You can ask for a chaperone.", "Your answers are private."],
  },
  pain_and_comfort: {
    title: "Comfort first",
    points: ["Most people feel pressure, not pain.", "You are in control. Say stop at any time and the nurse stops."],
  },
};

export const QUESTION_LABELS: Record<string, string> = {
  previous_screening: "Screened before",
  previously_treated: "Treated before",
  pregnant: "Could be pregnant",
  menstruating_now: "On period today",
  symptoms: "Symptoms",
  hiv_status: "HIV status",
  parity: "Births",
  smoker: "Smokes",
  contraception: "Family planning",
  phone: "Phone",
  result_channel: "Results by",
  consent: "Happy to go ahead",
};

export function answerText(answer: IntakeAnswer | undefined): string {
  if (!answer) return "";
  const { value } = answer;
  if (value === null || value === undefined) return answer.said || "Not sure";
  if (typeof value === "boolean") return value ? "Yes" : "No";
  if (Array.isArray(value)) return value.map((v) => v.replaceAll("_", " ")).join(", ") || "None";
  return String(value).replaceAll("_", " ");
}

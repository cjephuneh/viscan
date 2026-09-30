"use client";

import { useState } from "react";
import { type Intake, type IntakeEventType, sendIntakeEvent } from "@/lib/intake";

type Option = [value: string, label: string];
type Step = {
  id: string;
  prompt: string;
  hint?: string;
  type: IntakeEventType;
  kind: "text" | "number" | "tel" | "choice" | "multi" | "feeling";
  options?: Option[];
  toData: (value: string) => object;
};

const YES_NO_UNSURE: Option[] = [
  ["yes", "Yes"],
  ["no", "No"],
  ["unsure", "Not sure"],
];

const answer = (question: string) => (value: string) => ({ question, value, said: value });

const STEPS: Step[] = [
  { id: "name", prompt: "What's your name?", type: "details", kind: "text", toData: (v) => ({ full_name: v, preferred_name: v.split(" ")[0] }) },
  { id: "age", prompt: "How old are you?", type: "details", kind: "number", toData: (v) => ({ age: v }) },
  {
    id: "sex",
    prompt: "What sex were you assigned at birth?",
    type: "details",
    kind: "choice",
    options: [
      ["female", "Female"],
      ["male", "Male"],
      ["intersex", "Intersex"],
      ["prefer_not_to_say", "Prefer not to say"],
    ],
    toData: (v) => ({ sex: v }),
  },
  {
    id: "feeling",
    prompt: "How are you feeling about today's screening?",
    hint: "1 is completely relaxed, 5 is very nervous.",
    type: "feeling",
    kind: "feeling",
    toData: (v) => ({ level: Number(v) }),
  },
  {
    id: "previous_screening",
    prompt: "Have you been screened before?",
    type: "answer",
    kind: "choice",
    options: [
      ["never", "Never"],
      ["negative", "Yes, it was normal"],
      ["positive", "Yes, something was found"],
      ["unknown", "I don't know"],
    ],
    toData: answer("previous_screening"),
  },
  { id: "previously_treated", prompt: "Have you ever been treated on your cervix?", type: "answer", kind: "choice", options: YES_NO_UNSURE, toData: answer("previously_treated") },
  { id: "pregnant", prompt: "Could you be pregnant?", type: "answer", kind: "choice", options: YES_NO_UNSURE, toData: answer("pregnant") },
  { id: "menstruating_now", prompt: "Are you on your period today?", type: "answer", kind: "choice", options: YES_NO_UNSURE.slice(0, 2), toData: answer("menstruating_now") },
  {
    id: "symptoms",
    prompt: "Have you noticed any of these?",
    hint: "Choose all that apply.",
    type: "answer",
    kind: "multi",
    options: [
      ["postcoital_bleeding", "Bleeding after sex"],
      ["intermenstrual_bleeding", "Bleeding between periods"],
      ["postmenopausal_bleeding", "Bleeding after menopause"],
      ["abnormal_discharge", "Unusual discharge"],
      ["pelvic_pain", "Pelvic pain"],
      ["dyspareunia", "Pain during sex"],
    ],
    toData: (v) => ({ question: "symptoms", value: v || "none", said: v || "none" }),
  },
  {
    id: "hiv_status",
    prompt: "What is your HIV status?",
    hint: "Optional and private.",
    type: "answer",
    kind: "choice",
    options: [
      ["negative", "Negative"],
      ["positive", "Positive"],
      ["unknown", "I don't know"],
      ["prefer_not_to_say", "Prefer not to say"],
    ],
    toData: answer("hiv_status"),
  },
  { id: "parity", prompt: "How many children have you given birth to?", type: "answer", kind: "number", toData: answer("parity") },
  { id: "smoker", prompt: "Do you smoke?", type: "answer", kind: "choice", options: YES_NO_UNSURE.slice(0, 2), toData: answer("smoker") },
  { id: "phone", prompt: "Phone number for your results", hint: "Optional. Include the country code.", type: "answer", kind: "tel", toData: answer("phone") },
  {
    id: "result_channel",
    prompt: "How should we send your result?",
    type: "answer",
    kind: "choice",
    options: [
      ["sms", "SMS"],
      ["whatsapp", "WhatsApp"],
      ["none", "Don't send it"],
    ],
    toData: answer("result_channel"),
  },
  {
    id: "consent",
    prompt: "Are you happy to go ahead with the screening today?",
    hint: "You can change your mind at any time.",
    type: "answer",
    kind: "choice",
    options: YES_NO_UNSURE.slice(0, 2),
    toData: answer("consent"),
  },
];

const FACES = ["Relaxed", "Okay", "A little uneasy", "Nervous", "Very nervous"];

export function IntakeForm({ intake, onUpdate, onDone }: { intake: Intake; onUpdate: (intake: Intake) => void; onDone: (intake: Intake) => void }) {
  const [index, setIndex] = useState(0);
  const [value, setValue] = useState("");
  const [picked, setPicked] = useState<string[]>([]);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const step = STEPS[index];

  async function submit(raw: string | null) {
    setError("");
    setSaving(true);
    try {
      let latest = intake;
      if (raw !== null && raw.trim()) {
        latest = (await sendIntakeEvent(intake.id, step.type, step.toData(raw.trim()))).intake;
        onUpdate(latest);
      }
      setValue("");
      setPicked([]);
      if (index + 1 < STEPS.length) {
        setIndex(index + 1);
      } else {
        const done = await sendIntakeEvent(intake.id, "finish", { summary: "Completed the check-in form without the avatar." });
        onDone(done.intake);
      }
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setSaving(false);
    }
  }

  const optional = !["name", "age", "sex"].includes(step.id);

  return (
    <section className="intake-form" aria-labelledby="form-prompt">
      <div className="form-progress" aria-hidden="true">
        <span style={{ width: `${(index / STEPS.length) * 100}%` }} />
      </div>
      <p className="eyebrow">
        Question {index + 1} of {STEPS.length}
      </p>
      <h2 id="form-prompt">{step.prompt}</h2>
      {step.hint ? <p className="quiet">{step.hint}</p> : null}

      {step.kind === "choice" ? (
        <div className="choice-grid">
          {step.options!.map(([v, label]) => (
            <button key={v} type="button" className="choice" disabled={saving} onClick={() => submit(v)}>
              {label}
            </button>
          ))}
        </div>
      ) : step.kind === "feeling" ? (
        <div className="feeling-picker">
          {FACES.map((label, i) => (
            <button key={label} type="button" className={`feel-${i + 1}`} disabled={saving} onClick={() => submit(String(i + 1))}>
              <strong>{i + 1}</strong>
              <span>{label}</span>
            </button>
          ))}
        </div>
      ) : step.kind === "multi" ? (
        <>
          <div className="choice-grid">
            {step.options!.map(([v, label]) => (
              <button
                key={v}
                type="button"
                aria-pressed={picked.includes(v)}
                className={picked.includes(v) ? "choice on" : "choice"}
                onClick={() => setPicked((cur) => (cur.includes(v) ? cur.filter((p) => p !== v) : [...cur, v]))}
              >
                {label}
              </button>
            ))}
          </div>
          <div className="actions">
            <button type="button" className="primary" disabled={saving} onClick={() => submit(picked.join(",") || "none")}>
              {picked.length ? "Continue" : "None of these"}
            </button>
          </div>
        </>
      ) : (
        <form
          className="form-answer"
          onSubmit={(event) => {
            event.preventDefault();
            if (value.trim()) submit(value);
          }}
        >
          <input
            aria-label={step.prompt}
            type={step.kind}
            inputMode={step.kind === "number" ? "numeric" : undefined}
            value={value}
            onChange={(event) => setValue(event.target.value)}
            autoFocus
          />
          <button type="submit" className="primary" disabled={saving || !value.trim()}>
            Continue
          </button>
        </form>
      )}

      {error ? <p className="error">{error}</p> : null}
      <div className="form-nav">
        {index > 0 ? (
          <button type="button" className="ghost" disabled={saving} onClick={() => setIndex(index - 1)}>
            Back
          </button>
        ) : (
          <span />
        )}
        {optional ? (
          <button type="button" className="ghost" disabled={saving} onClick={() => submit(null)}>
            Skip
          </button>
        ) : null}
      </div>
    </section>
  );
}

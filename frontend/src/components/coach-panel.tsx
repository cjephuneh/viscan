"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { CervixClock } from "@/components/cervix-clock";
import { TeachingCard } from "@/components/teaching-card";
import {
  type ActionStep,
  type CoachEventType,
  type CoachSession,
  type QuizItem,
  type Roleplay,
  getCoachPersona,
  getCoachToken,
  sendCoachEvent,
  startCoachSession,
} from "@/lib/coach";
import { type ToolHandlers, useAnamAvatar } from "@/lib/use-anam";
import type { Interpretation } from "@/lib/viscan";

type Stage = "intro" | "live" | "ended";
type Focus = { clock_start: number; clock_end: number; label?: string };

const VIDEO_ID = "coach-video";
const LETTERS = ["A", "B", "C", "D"];
const PROMPTS = [
  { label: "Walk me through it", text: "Please walk me through this result step by step." },
  { label: "What do I do next?", text: "What exactly should I do next for this patient?" },
  { label: "Quiz me", text: "Quiz me on this case." },
  { label: "Practise telling the patient", text: "Let me practise explaining this result to the patient. You play the patient." },
];
const PRACTICE_PROMPTS = [
  { label: "How do I read VIA?", text: "Teach me how to read a VIA image." },
  { label: "When can I ablate?", text: "When can I treat with thermal ablation, and when must I refer?" },
  { label: "Quiz me", text: "Quiz me with a practice case." },
  { label: "Practise counselling", text: "Let me practise telling a patient her VIA result is positive. You play the patient." },
];

const spoken = (text: string) =>
  text
    .replace(/\[[a-z_]+\]\s*\{[^}]*\}/gi, "")
    .replace(/\[[a-z]+\]\s*/gi, "")
    .trim();

function glow(section: string) {
  const el = document.querySelector<HTMLElement>(`[data-coach="${section}"]`);
  if (!el) return false;
  el.scrollIntoView({ behavior: "smooth", block: "center" });
  el.classList.remove("coach-glow");
  void el.offsetWidth;
  el.classList.add("coach-glow");
  window.setTimeout(() => el.classList.remove("coach-glow"), 5000);
  return true;
}

function QuizCard({ quiz, onAnswer }: { quiz: QuizItem; onAnswer: (index: number) => void }) {
  const answered = quiz.chosen_index !== null;
  return (
    <article className="quiz-card" aria-labelledby="quiz-q">
      <p className="eyebrow">Quick check</p>
      <h3 id="quiz-q">{quiz.question}</h3>
      <div className="quiz-options">
        {quiz.options.map((option, i) => {
          const state = !answered ? "" : i === quiz.correct_index ? "right" : i === quiz.chosen_index ? "wrong" : "dim";
          return (
            <button key={option} type="button" className={`quiz-option ${state}`} disabled={answered} onClick={() => onAnswer(i)}>
              <span className="quiz-letter">{LETTERS[i]}</span>
              {option}
            </button>
          );
        })}
      </div>
      {answered ? (
        <p className={quiz.correct ? "quiz-result right" : "quiz-result wrong"}>
          {quiz.correct ? "Correct. " : "Not quite. "}
          {quiz.explanation}
        </p>
      ) : null}
    </article>
  );
}

function RoleplayCard({ roleplay, personaName }: { roleplay: Roleplay; personaName: string }) {
  const finished = roleplay.improve !== null && roleplay.improve !== undefined;
  return (
    <article className={finished ? "roleplay-card done" : "roleplay-card"}>
      <p className="eyebrow">{finished ? "Role-play feedback" : `Role-play · ${personaName} is the patient`}</p>
      <h3>{roleplay.scenario || "Explaining the result"}</h3>
      {finished ? (
        <>
          <ul className="roleplay-strengths">
            {roleplay.strengths.map((s) => (
              <li key={s}>{s}</li>
            ))}
          </ul>
          <p className="roleplay-improve">
            <strong>Try next time:</strong> {roleplay.improve}
          </p>
        </>
      ) : (
        <p className="quiet small">Speak to her as you would to your patient. Say “stop the role-play” to get feedback.</p>
      )}
    </article>
  );
}

function ActionPlan({ steps, onToggle }: { steps: ActionStep[]; onToggle: (index: number, done: boolean) => void }) {
  if (!steps.length) return null;
  return (
    <section className="action-plan" aria-labelledby="plan-title">
      <h3 id="plan-title" className="block-title">
        Action plan
      </h3>
      <ol>
        {steps.map((step, i) => (
          <li key={`${step.step}-${i}`} className={step.done ? "done" : ""}>
            <label>
              <input type="checkbox" checked={step.done} onChange={(event) => onToggle(i, event.target.checked)} />
              <span>
                <strong>{step.step}</strong>
                {step.why ? <small>{step.why}</small> : null}
              </span>
            </label>
          </li>
        ))}
      </ol>
    </section>
  );
}

export function CoachPanel({
  interpretation,
  clinicianId,
  variant = "dock",
  onClose,
}: {
  interpretation?: Interpretation | null;
  clinicianId?: string;
  variant?: "dock" | "page";
  onClose?: () => void;
}) {
  const avatar = useAnamAvatar(VIDEO_ID);
  const { historyRef, sessionIdRef, stop: stopAvatar } = avatar;
  const [stage, setStage] = useState<Stage>("intro");
  const [persona, setPersona] = useState({ available: true, name: "Kezia", image_url: null as string | null });
  const [session, setSession] = useState<CoachSession | null>(null);
  const [card, setCard] = useState<string | null>(null);
  const [focus, setFocus] = useState<Focus | null>(null);
  const [view, setView] = useState<"card" | "quiz" | "roleplay" | null>(null);
  const [error, setError] = useState("");
  const [starting, setStarting] = useState(false);
  const [typed, setTyped] = useState("");
  const sessionRef = useRef<CoachSession | null>(null);

  const name = persona.name;
  const quiz = session?.quiz.at(-1) ?? null;
  const roleplay = session?.roleplays.at(-1) ?? null;
  const lesions = useMemo(() => interpretation?.lesions ?? [], [interpretation]);
  const prompts = interpretation ? PROMPTS : PRACTICE_PROMPTS;

  useEffect(() => {
    getCoachPersona()
      .then(setPersona)
      .catch(() => setPersona((p) => ({ ...p, available: false })));
  }, []);

  const keep = useCallback((next: CoachSession) => {
    sessionRef.current = next;
    setSession(next);
  }, []);

  const record = useCallback(
    async (type: CoachEventType, data: object) => {
      const current = sessionRef.current;
      if (!current) return "Noted.";
      const res = await sendCoachEvent(current.id, type, data, sessionIdRef.current);
      keep(res.session);
      return res.message;
    },
    [keep, sessionIdRef],
  );

  const saveTranscript = useCallback(async () => {
    const current = sessionRef.current;
    if (current && historyRef.current.length) {
      await sendCoachEvent(current.id, "transcript", { messages: historyRef.current }).catch(() => undefined);
    }
  }, [historyRef]);

  const tools: ToolHandlers = useMemo(
    () => ({
      highlight_section: async (args) => {
        const found = glow(String(args.section));
        const message = await record("highlight", args);
        return found ? message : `${message} (That section is not on screen right now.)`;
      },
      point_to_lesion: (args) => {
        setFocus({ clock_start: Number(args.clock_start), clock_end: Number(args.clock_end), label: args.label ? String(args.label) : undefined });
        return record("lesion", args);
      },
      show_teaching_card: (args) => {
        setCard(String(args.card));
        setView("card");
        return record("card", args);
      },
      add_action_step: (args) => record("action_step", args),
      ask_quiz: (args) => {
        setView("quiz");
        return record("quiz_asked", args);
      },
      start_roleplay: (args) => {
        setView("roleplay");
        return record("roleplay_start", args);
      },
      end_roleplay: (args) => {
        setView("roleplay");
        return record("roleplay_end", args);
      },
      note_learning: (args) => record("learning", args),
      finish_lesson: async (args) => {
        const message = await record("finish", args);
        saveTranscript();
        return message;
      },
    }),
    [record, saveTranscript],
  );

  async function begin() {
    setStarting(true);
    setError("");
    try {
      const created = await startCoachSession(interpretation?.interpretation_id ?? null, clinicianId);
      keep(created);
      setStage("live");
      const token = await getCoachToken(created.id);
      setPersona((p) => ({ ...p, ...token.persona, available: true }));
      await avatar.start(token.session_token, tools);
    } catch (err) {
      setStage("intro");
      setError((err as Error).message);
    } finally {
      setStarting(false);
    }
  }

  async function end() {
    await stopAvatar();
    await saveTranscript();
    setStage("ended");
  }

  async function answer(index: number) {
    const current = sessionRef.current?.quiz.at(-1);
    if (!current) return;
    await record("quiz_answer", { chosen_index: index }).catch(() => undefined);
    avatar.say(`My answer is ${LETTERS[index]}: ${current.options[index]}`);
  }

  async function toggleStep(index: number, done: boolean) {
    await record("action_done", { index, done }).catch(() => undefined);
  }

  const live = avatar.status === "live";
  const shownError = error || (avatar.status === "error" ? avatar.error || `Lost the connection to ${name}.` : "");
  const score = session?.score;

  return (
    <aside className={`coach coach-${variant}`} aria-label={`${name}, AI clinical coach`}>
      <header className="coach-head">
        <div className="coach-id">
          {persona.image_url ? <img src={persona.image_url} alt="" /> : <span className="coach-avatar-fallback">{name[0]}</span>}
          <div>
            <strong>{name}</strong>
            <span>AI clinical coach</span>
          </div>
        </div>
        <div className="coach-head-actions">
          {score && score.answered ? (
            <span className="coach-score" aria-label={`Quiz score ${score.correct} of ${score.answered}`}>
              {score.correct}/{score.answered}
            </span>
          ) : null}
          {onClose ? (
            <button
              type="button"
              className="coach-close"
              aria-label="Close coach"
              onClick={async () => {
                if (stage === "live") await end();
                onClose();
              }}
            >
              ×
            </button>
          ) : null}
        </div>
      </header>

      {stage === "intro" ? (
        <div className="coach-intro">
          <p className="coach-pitch">
            {interpretation
              ? `Not sure what this reading means or what to do next? ${name} has studied this case and can walk you through it, quiz you, or let you rehearse telling the patient.`
              : `Practise reading VIA results and managing positive screens with ${name}, then test yourself with a quiz or a role-play.`}
          </p>
          <ul className="coach-skills">
            <li>Points at each part of the result as she explains it</li>
            <li>Builds a step-by-step action plan</li>
            <li>Quizzes you and keeps score</li>
            <li>Plays the patient so you can practise counselling</li>
          </ul>
          <button type="button" className="primary big" onClick={begin} disabled={starting || !persona.available}>
            {starting ? "Starting…" : `Start lesson with ${name}`}
          </button>
          <p className="quiet small">
            {persona.available
              ? `${name} is an AI coach. She teaches from WHO guidance and this reading; you make the clinical decision.`
              : `${name} is offline right now.`}
          </p>
          {error ? <p className="error">{error}</p> : null}
        </div>
      ) : null}

      {stage !== "intro" ? (
        <>
          <div className={`coach-stage ${avatar.speaking ? "speaking" : ""} ${avatar.listening ? "listening" : ""}`}>
            {persona.image_url ? <img className="stage-poster" src={persona.image_url} alt="" aria-hidden="true" /> : null}
            <video id={VIDEO_ID} autoPlay playsInline className={live ? "on" : ""} />
            <p className="stage-status" role="status">
              <span className="status-dot" aria-hidden="true" />
              {stage === "ended"
                ? "Lesson ended"
                : !live
                  ? `Connecting to ${name}…`
                  : avatar.listening
                    ? "Listening…"
                    : avatar.speaking
                      ? `${name} is speaking`
                      : "Ask anything"}
            </p>
            {spoken(avatar.caption) && live ? <p className="stage-caption">{spoken(avatar.caption)}</p> : null}
          </div>

          {stage === "live" ? (
            <>
              <div className="coach-prompts">
                {prompts.map((p) => (
                  <button key={p.label} type="button" className="control" disabled={!live} onClick={() => avatar.say(p.text)}>
                    {p.label}
                  </button>
                ))}
              </div>
              <form
                className="type-box"
                onSubmit={(event) => {
                  event.preventDefault();
                  if (avatar.say(typed)) setTyped("");
                }}
              >
                <input
                  aria-label={`Ask ${name}`}
                  placeholder={`Ask ${name} about this result…`}
                  value={typed}
                  onChange={(event) => setTyped(event.target.value)}
                  disabled={!live}
                />
                <button type="submit" className="primary" disabled={!live || !typed.trim()}>
                  Ask
                </button>
              </form>
              <div className="coach-controls">
                <button type="button" className={avatar.muted ? "control on" : "control"} onClick={avatar.toggleMute} disabled={!live} aria-pressed={avatar.muted}>
                  {avatar.muted ? "Unmute mic" : "Mute mic"}
                </button>
                <button type="button" className="control end" onClick={end}>
                  End lesson
                </button>
              </div>
            </>
          ) : null}
          {shownError ? <p className="error">{shownError}</p> : null}

          <div className="coach-board">
            {view === "quiz" && quiz ? <QuizCard quiz={quiz} onAnswer={answer} /> : null}
            {view === "roleplay" && roleplay ? <RoleplayCard roleplay={roleplay} personaName={name} /> : null}
            {view === "card" && card ? <TeachingCard card={card} /> : null}
            {interpretation && (lesions.length || focus) ? <CervixClock lesions={lesions} focus={focus} /> : null}
            <ActionPlan steps={session?.action_plan ?? []} onToggle={toggleStep} />
            {stage === "ended" && session ? (
              <section className="coach-summary" aria-labelledby="coach-summary-title">
                <h3 id="coach-summary-title" className="block-title">
                  Lesson summary
                </h3>
                {session.summary ? <p>{session.summary}</p> : null}
                <p>
                  {session.score.answered
                    ? `Quiz: ${session.score.correct} of ${session.score.answered} correct.`
                    : "No quiz this time."}{" "}
                  {session.topics.length ? `Covered: ${session.topics.map((t) => t.topic).join(", ")}.` : ""}
                </p>
                <button type="button" className="secondary" onClick={() => { setStage("intro"); setSession(null); sessionRef.current = null; setView(null); setFocus(null); }}>
                  New lesson
                </button>
              </section>
            ) : null}
          </div>
        </>
      ) : null}
    </aside>
  );
}

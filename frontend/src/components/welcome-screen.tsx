"use client";

import Link from "next/link";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { BreathingGuide } from "@/components/breathing-guide";
import { IntakeForm } from "@/components/intake-form";
import { TopicCard } from "@/components/topic-card";
import {
  type Intake,
  type IntakeEventType,
  QUESTION_LABELS,
  TOPICS,
  answerText,
  getAvatarPersona,
  getAvatarToken,
  sendIntakeEvent,
  startIntake,
} from "@/lib/intake";
import { type ToolHandlers, useAnamAvatar } from "@/lib/use-anam";

type Mode = "intro" | "avatar" | "form" | "done";
type Persona = { available: boolean; name: string; image_url: string | null };

const VIDEO_ID = "mia-video";
const FEELING_WORDS = ["", "Relaxed", "Okay", "A little uneasy", "Nervous", "Very nervous"];
const AUTO_END_AFTER_FINISH_MS = 45_000;

const spoken = (text: string) =>
  text
    .replace(/\[[a-z_]+\]\s*\{[^}]*\}/gi, "")
    .replace(/\[[a-z]+\]\s*/gi, "")
    .trim();

function journey(intake: Intake | null) {
  const answered = Object.keys(intake?.answers ?? {}).length;
  const steps = [
    { label: "Say hello", done: Boolean(intake?.full_name || intake?.preferred_name) && intake?.age != null && Boolean(intake?.sex) },
    { label: "How you feel", done: (intake?.feelings.length ?? 0) > 0 },
    { label: "About VIA", done: (intake?.topics_covered.length ?? 0) >= 2 },
    { label: "A few questions", done: answered >= 6 || Boolean(intake?.answers.consent) },
    { label: "Ready for the nurse", done: intake?.status === "completed" },
  ];
  const current = steps.findIndex((step) => !step.done);
  return steps.map((step, i) => ({ ...step, state: step.done ? "done" : i === current ? "active" : "" }));
}

function FeelingMeter({ intake }: { intake: Intake }) {
  const { start, end } = intake.anxiety;
  if (start == null) return null;
  return (
    <div className="feeling-meter" aria-label={`Feeling ${end ?? start} out of 5`}>
      <div className="meter-track">
        {[1, 2, 3, 4, 5].map((n) => (
          <span key={n} className={`meter-dot feel-${n} ${n === (end ?? start) ? "on" : ""} ${n === start && end != null && end !== start ? "was" : ""}`} />
        ))}
      </div>
      <p>
        {end != null && end !== start ? (
          <>
            {FEELING_WORDS[start]} <span aria-hidden="true">→</span> <strong>{FEELING_WORDS[end]}</strong>
          </>
        ) : (
          <strong>{FEELING_WORDS[end ?? start]}</strong>
        )}
      </p>
    </div>
  );
}

function VisitCard({ intake, persona }: { intake: Intake | null; persona: string }) {
  const answers = Object.entries(intake?.answers ?? {}).filter(([q]) => q !== "consent");
  const name = intake?.preferred_name || intake?.full_name;
  return (
    <section className="visit-card" aria-labelledby="visit-card-title">
      <div className="visit-card-head">
        <p className="eyebrow">Your visit card</p>
        <h3 id="visit-card-title">{name ? `Hi, ${name}` : "Filling in as we talk"}</h3>
      </div>
      <dl className="visit-facts">
        <div className={intake?.age != null ? "filled" : ""}>
          <dt>Age</dt>
          <dd>{intake?.age ?? "—"}</dd>
        </div>
        <div className={intake?.sex ? "filled" : ""}>
          <dt>Sex</dt>
          <dd>{intake?.sex ? intake.sex.replaceAll("_", " ") : "—"}</dd>
        </div>
      </dl>
      {intake ? <FeelingMeter intake={intake} /> : null}
      {answers.length ? (
        <ul className="visit-answers">
          {answers.map(([question, a]) => (
            <li key={question}>
              <span>{QUESTION_LABELS[question] ?? question}</span>
              <strong>{answerText(a)}</strong>
            </li>
          ))}
        </ul>
      ) : (
        <p className="quiet small">{persona} will note your answers here. Only your nurse sees them.</p>
      )}
      {intake?.concerns.length ? (
        <p className="visit-note">
          {intake.concerns.length === 1 ? "1 worry" : `${intake.concerns.length} worries`} shared with the nurse
        </p>
      ) : null}
    </section>
  );
}

function CheckInCode({ code }: { code: string }) {
  return (
    <p className="checkin-code" aria-label={`Check-in code ${code.split("").join(" ")}`}>
      {code.split("").map((ch, i) => (
        <span key={i} style={{ animationDelay: `${i * 90}ms` }}>
          {ch}
        </span>
      ))}
    </p>
  );
}

function DonePanel({ intake, onRestart }: { intake: Intake; onRestart: () => void }) {
  const name = intake.preferred_name || intake.full_name;
  const { start, end } = intake.anxiety;
  return (
    <section className="done-panel" aria-labelledby="done-title">
      <p className="eyebrow">You&apos;re all set</p>
      <h2 id="done-title">{name ? `Thank you, ${name}.` : "Thank you."}</h2>
      <p className="lede">Show this code to the nurse when you are called in.</p>
      <CheckInCode code={intake.code} />
      {start != null && end != null && end < start ? (
        <p className="done-calm">
          You arrived feeling <strong>{FEELING_WORDS[start].toLowerCase()}</strong> and now feel{" "}
          <strong>{FEELING_WORDS[end].toLowerCase()}</strong>. That&apos;s great progress.
        </p>
      ) : null}
      <ol className="next-steps">
        <li>
          <strong>Take a seat</strong>
          <span>The nurse already has your answers, so you won&apos;t need to repeat them.</span>
        </li>
        <li>
          <strong>About five minutes</strong>
          <span>The exam is quick. You can ask the nurse to pause or stop at any time.</span>
        </li>
        <li>
          <strong>Result today</strong>
          <span>
            {intake.prefill.result_channel && intake.prefill.result_channel !== "none"
              ? `We'll also send it to you by ${intake.prefill.result_channel === "sms" ? "SMS" : "WhatsApp"}.`
              : "The nurse will talk you through it before you leave."}
          </span>
        </li>
      </ol>
      {intake.topics_covered.length ? (
        <div className="learned">
          <p className="eyebrow">What you learned</p>
          <ul>
            {intake.topics_covered.map((t) => (
              <li key={t}>{TOPICS[t]?.title ?? t}</li>
            ))}
          </ul>
        </div>
      ) : null}
      <div className="actions">
        <button type="button" className="primary" onClick={onRestart}>
          Next person
        </button>
        <Link className="ghost link-button" href={`/screening?intake=${intake.id}`}>
          Staff: open screening
        </Link>
      </div>
    </section>
  );
}

export function WelcomeScreen() {
  const avatar = useAnamAvatar(VIDEO_ID);
  const { historyRef, sessionIdRef, stop: stopAvatar } = avatar;
  const [mode, setMode] = useState<Mode>("intro");
  const [persona, setPersona] = useState<Persona | null>(null);
  const [intake, setIntake] = useState<Intake | null>(null);
  const [topic, setTopic] = useState<string | null>(null);
  const [breathing, setBreathing] = useState<{ rounds: number; key: number } | null>(null);
  const [notice, setNotice] = useState("");
  const [starting, setStarting] = useState(false);
  const [typed, setTyped] = useState("");
  const [showChat, setShowChat] = useState(false);
  const intakeRef = useRef<Intake | null>(null);
  const finishTimer = useRef<number | null>(null);

  const personaName = persona?.name || "Mia";
  const steps = useMemo(() => journey(intake), [intake]);

  useEffect(() => {
    getAvatarPersona()
      .then(setPersona)
      .catch(() => setPersona({ available: false, name: "Mia", image_url: null }));
  }, []);

  const keep = useCallback((next: Intake) => {
    intakeRef.current = next;
    setIntake(next);
  }, []);

  const record = useCallback(
    async (type: IntakeEventType, data: object) => {
      const current = intakeRef.current;
      if (!current) return "Noted.";
      const res = await sendIntakeEvent(current.id, type, data, sessionIdRef.current);
      keep(res.intake);
      return res.message;
    },
    [sessionIdRef, keep],
  );

  const saveTranscript = useCallback(async () => {
    const current = intakeRef.current;
    const messages = historyRef.current;
    if (!current || !messages.length) return;
    await sendIntakeEvent(current.id, "transcript", { messages }).catch(() => undefined);
  }, [historyRef]);

  const endSession = useCallback(async () => {
    if (finishTimer.current) window.clearTimeout(finishTimer.current);
    finishTimer.current = null;
    await stopAvatar();
    await saveTranscript();
    setBreathing(null);
    setMode(intakeRef.current?.status === "completed" ? "done" : "form");
    if (intakeRef.current?.status !== "completed") {
      setNotice("Let's finish the last few questions here. Anything you already told Mia is saved.");
    }
  }, [stopAvatar, saveTranscript]);

  const tools: ToolHandlers = useMemo(
    () => ({
      save_patient_details: (args) => record("details", args),
      save_answer: (args) => record("answer", args),
      record_feeling: (args) => record("feeling", args),
      show_topic: (args) => {
        setTopic(String(args.topic ?? ""));
        return record("topic", args);
      },
      start_breathing_exercise: (args) => {
        const rounds = Math.max(1, Math.min(5, Number(args.rounds) || 3));
        setBreathing({ rounds, key: Date.now() });
        return record("breathing", args);
      },
      note_concern: (args) => record("concern", args),
      log_patient_question: (args) => record("question", args),
      finish_intake: async (args) => {
        const message = await record("finish", args);
        setTopic(null);
        saveTranscript();
        finishTimer.current = window.setTimeout(() => endSession(), AUTO_END_AFTER_FINISH_MS);
        return message;
      },
    }),
    [record, saveTranscript, endSession],
  );

  async function meetMia() {
    setStarting(true);
    setNotice("");
    try {
      const created = await startIntake("avatar");
      keep(created);
      setMode("avatar");
      try {
        const token = await getAvatarToken(created.id);
        if (token.persona) setPersona((p) => ({ available: true, ...p, ...token.persona }));
        await avatar.start(token.session_token, tools);
      } catch {
        setMode("form");
        setNotice(`${personaName} can't join right now, so let's use a short form instead. It takes about three minutes.`);
      }
    } catch (err) {
      setNotice((err as Error).message);
    } finally {
      setStarting(false);
    }
  }

  async function useForm() {
    setStarting(true);
    setNotice("");
    try {
      keep(await startIntake("form"));
      setMode("form");
    } catch (err) {
      setNotice((err as Error).message);
    } finally {
      setStarting(false);
    }
  }

  function restart() {
    intakeRef.current = null;
    setIntake(null);
    setTopic(null);
    setBreathing(null);
    setNotice("");
    setTyped("");
    setShowChat(false);
    setMode("intro");
  }

  useEffect(() => {
    if (avatar.status === "error" && mode === "avatar") {
      saveTranscript();
      setMode(intakeRef.current?.status === "completed" ? "done" : "form");
      setNotice(`${avatar.error || `We lost the connection to ${personaName}.`} Let's carry on here. Your answers so far are saved.`);
    }
  }, [avatar.status, avatar.error, mode, personaName, saveTranscript]);

  useEffect(() => {
    return () => {
      if (finishTimer.current) window.clearTimeout(finishTimer.current);
    };
  }, []);

  const connecting = mode === "avatar" && avatar.status !== "live";
  const finished = intake?.status === "completed";

  return (
    <div className="welcome">
      <div className="welcome-glow" aria-hidden="true" />
      <header className="welcome-top">
        <p className="welcome-brand">
          <span className="mark-dot" aria-hidden="true" /> VISCAN
        </p>
        <Link href="/screening" className="staff-link">
          Staff: screening workstation →
        </Link>
      </header>

      {mode === "intro" ? (
        <main className="welcome-intro">
          <div className="intro-copy">
            <p className="eyebrow">Before your screening</p>
            <h1>
              Meet <em>{personaName}</em>, your guide for today.
            </h1>
            <p className="lede">
              {personaName} is a friendly AI guide. In about five minutes, she&apos;ll explain what VIA screening is,
              what will happen in the room, and answer your questions, so you walk in calm and ready. A real nurse
              does the check itself.
            </p>
            <ul className="intro-pills">
              <li>About 5 minutes</li>
              <li>Talk or type</li>
              <li>Private: only your nurse sees your answers</li>
            </ul>
            <div className="intro-actions">
              <button type="button" className="primary big" onClick={meetMia} disabled={starting || persona?.available === false}>
                {starting ? "Getting ready…" : `Meet ${personaName}`}
              </button>
              <button type="button" className="ghost" onClick={useForm} disabled={starting}>
                I&apos;d rather fill in a short form
              </button>
            </div>
            <p className="quiet small">
              {persona?.available === false
                ? `${personaName} is offline right now. The short form asks the same questions.`
                : "Your browser will ask to use the microphone so she can hear you."}
            </p>
            {notice ? <p className="error">{notice}</p> : null}
          </div>
          <div className="intro-portrait" aria-hidden="true">
            <div className="portrait-halo" />
            {persona?.image_url ? <img src={persona.image_url} alt="" /> : <div className="portrait-fallback">{personaName[0]}</div>}
            <div className="portrait-bubble">
              <span className="typing-dots">
                <i />
                <i />
                <i />
              </span>
              Hi! I&apos;m {personaName}.
            </div>
          </div>
        </main>
      ) : null}

      {mode === "avatar" ? (
        <main className="welcome-live">
          <section className="avatar-column" aria-label={`Conversation with ${personaName}`}>
            <div className={`avatar-stage ${avatar.speaking ? "speaking" : ""} ${avatar.listening ? "listening" : ""}`}>
              {persona?.image_url ? <img className="stage-poster" src={persona.image_url} alt="" aria-hidden="true" /> : null}
              <video id={VIDEO_ID} autoPlay playsInline className={avatar.status === "live" ? "on" : ""} />
              <p className="stage-status" role="status">
                <span className="status-dot" aria-hidden="true" />
                {connecting
                  ? `Connecting to ${personaName}…`
                  : avatar.listening
                    ? "Listening…"
                    : avatar.speaking
                      ? `${personaName} is speaking`
                      : avatar.muted
                        ? "Microphone off: type below"
                        : "Your turn: just speak"}
              </p>
              <span className="ai-badge">AI guide</span>
              {spoken(avatar.caption) && avatar.status === "live" ? (
                <p className="stage-caption" aria-live="polite">
                  {spoken(avatar.caption)}
                </p>
              ) : null}
              {breathing ? (
                <BreathingGuide key={breathing.key} rounds={breathing.rounds} onClose={() => setBreathing(null)} />
              ) : null}
            </div>

            <div className="stage-controls">
              <button type="button" className={avatar.muted ? "control on" : "control"} onClick={avatar.toggleMute} disabled={avatar.status !== "live"} aria-pressed={avatar.muted}>
                {avatar.muted ? "Unmute mic" : "Mute mic"}
              </button>
              <button
                type="button"
                className="control calm"
                disabled={avatar.status !== "live"}
                onClick={() => avatar.say("I'm feeling a bit nervous about this.")}
              >
                I&apos;m feeling nervous
              </button>
              <button type="button" className="control" disabled={avatar.status !== "live"} onClick={() => avatar.say("Sorry, could you say that again?")}>
                Say that again
              </button>
              <button type="button" className="control end" onClick={endSession}>
                {finished ? "Finish" : "End chat"}
              </button>
            </div>

            <form
              className="type-box"
              onSubmit={(event) => {
                event.preventDefault();
                if (avatar.say(typed)) setTyped("");
              }}
            >
              <input
                aria-label={`Type a message to ${personaName}`}
                placeholder={`Prefer typing? Write to ${personaName}…`}
                value={typed}
                onChange={(event) => setTyped(event.target.value)}
                disabled={avatar.status !== "live"}
              />
              <button type="submit" className="primary" disabled={avatar.status !== "live" || !typed.trim()}>
                Send
              </button>
            </form>
            {avatar.error ? <p className="error">{avatar.error}</p> : null}

            <button type="button" className="chat-toggle" onClick={() => setShowChat((s) => !s)} aria-expanded={showChat}>
              {showChat ? "Hide conversation" : "Show conversation"}
            </button>
            {showChat ? (
              <ol className="chat-log">
                {avatar.history.map((line, i) => (
                  <li key={i} className={line.role}>
                    <span>{line.role === "persona" ? personaName : "You"}</span>
                    {spoken(line.content)}
                  </li>
                ))}
              </ol>
            ) : null}
          </section>

          <aside className="guide-column">
            <ol className="journey" aria-label="Your check-in">
              {steps.map((step, i) => (
                <li key={step.label} className={step.state}>
                  <span className="journey-dot" aria-hidden="true">
                    {step.done ? "✓" : i + 1}
                  </span>
                  {step.label}
                </li>
              ))}
            </ol>

            {finished && intake ? (
              <section className="done-mini">
                <p className="eyebrow">Your check-in code</p>
                <CheckInCode code={intake.code} />
                <p className="quiet small">Show this to the nurse. {personaName} will say goodbye in a moment.</p>
              </section>
            ) : topic ? (
              <TopicCard topic={topic} />
            ) : (
              <article className="topic-card placeholder">
                <p className="eyebrow">While you talk</p>
                <h3>Pictures appear here</h3>
                <p className="quiet">When {personaName} explains a step, you&apos;ll see it here too.</p>
              </article>
            )}

            <VisitCard intake={intake} persona={personaName} />
          </aside>
        </main>
      ) : null}

      {mode === "form" && intake ? (
        <main className="welcome-form">
          {notice ? <p className="notice">{notice}</p> : null}
          <IntakeForm
            intake={intake}
            onUpdate={keep}
            onDone={(done) => {
              keep(done);
              setMode("done");
            }}
          />
          <VisitCard intake={intake} persona={personaName} />
        </main>
      ) : null}

      {mode === "done" && intake ? (
        <main className="welcome-done">
          <DonePanel intake={intake} onRestart={restart} />
        </main>
      ) : null}

      <footer className="welcome-foot">
        {personaName} is an AI assistant and does not give diagnoses. If you are in pain or bleeding heavily, tell the
        front desk right away.
      </footer>
    </div>
  );
}

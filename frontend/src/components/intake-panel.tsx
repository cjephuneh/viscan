"use client";

import { useEffect, useState } from "react";
import { type Intake, QUESTION_LABELS, TOPICS, answerText, getIntakeByCode, listWaitingIntakes } from "@/lib/intake";

const FEELING_WORDS = ["", "relaxed", "okay", "a little uneasy", "nervous", "very nervous"];

function minutesAgo(iso: string | null) {
  if (!iso) return "";
  const mins = Math.max(0, Math.round((Date.now() - new Date(iso).getTime()) / 60000));
  return mins < 1 ? "just now" : mins < 60 ? `${mins} min ago` : `${Math.round(mins / 60)} h ago`;
}

export function IntakeSummary({ intake, onClear }: { intake: Intake; onClear: () => void }) {
  const name = intake.full_name || intake.preferred_name || "Patient";
  const { start, end } = intake.anxiety;
  return (
    <article className="intake-summary" aria-labelledby="intake-summary-title">
      <header>
        <div>
          <p className="eyebrow">
            Checked in with {intake.channel === "avatar" ? "Mia, the AI guide" : "the check-in form"} · code {intake.code}
          </p>
          <h2 id="intake-summary-title">
            {name}
            {intake.age != null ? `, ${intake.age}` : ""}
            {intake.sex ? ` · ${intake.sex.replaceAll("_", " ")}` : ""}
          </h2>
        </div>
        <button type="button" className="ghost" onClick={onClear}>
          Clear
        </button>
      </header>

      {intake.flags.length ? (
        <ul className="intake-flags">
          {intake.flags.map((flag) => (
            <li key={flag.text} className={flag.level}>
              {flag.text}
            </li>
          ))}
        </ul>
      ) : null}

      <div className="intake-grid">
        {start != null ? (
          <div>
            <h3 className="block-title">Feeling</h3>
            <p>
              Arrived {FEELING_WORDS[start]} ({start}/5)
              {end != null && end !== start ? `, now ${FEELING_WORDS[end]} (${end}/5)` : ""}.
              {intake.breathing_exercises ? ` Did ${intake.breathing_exercises} breathing exercise${intake.breathing_exercises > 1 ? "s" : ""}.` : ""}
            </p>
          </div>
        ) : null}
        {intake.summary ? (
          <div>
            <h3 className="block-title">Summary for you</h3>
            <p>{intake.summary}</p>
          </div>
        ) : null}
        {Object.keys(intake.answers).length ? (
          <div>
            <h3 className="block-title">What they told us</h3>
            <dl className="intake-answers">
              {Object.entries(intake.answers).map(([q, a]) => (
                <div key={q}>
                  <dt>{QUESTION_LABELS[q] ?? q}</dt>
                  <dd title={a.said}>{answerText(a)}</dd>
                </div>
              ))}
            </dl>
          </div>
        ) : null}
        {intake.topics_covered.length ? (
          <div>
            <h3 className="block-title">Already explained</h3>
            <p>{intake.topics_covered.map((t) => TOPICS[t]?.title ?? t).join(" · ")}</p>
          </div>
        ) : null}
      </div>
      <p className="quiet small">Visit details below were filled in from the check-in. Check them with the patient.</p>
    </article>
  );
}

export function CheckedInPatients({ onSelect }: { onSelect: (intake: Intake) => void }) {
  const [waiting, setWaiting] = useState<Intake[]>([]);
  const [code, setCode] = useState("");
  const [error, setError] = useState("");

  useEffect(() => {
    let active = true;
    const load = () =>
      listWaitingIntakes()
        .then((list) => active && setWaiting(list))
        .catch(() => undefined);
    load();
    const timer = window.setInterval(load, 20000);
    return () => {
      active = false;
      window.clearInterval(timer);
    };
  }, []);

  async function lookup(event: React.FormEvent) {
    event.preventDefault();
    if (!code.trim()) return;
    setError("");
    try {
      onSelect(await getIntakeByCode(code));
      setCode("");
    } catch (err) {
      setError((err as Error).message);
    }
  }

  return (
    <section className="checked-in" aria-labelledby="checked-in-title">
      <div className="checked-in-head">
        <h2 id="checked-in-title" className="block-title">
          Checked in and waiting
        </h2>
        <form className="code-lookup" onSubmit={lookup}>
          <input
            aria-label="Check-in code"
            placeholder="Check-in code"
            value={code}
            maxLength={5}
            onChange={(event) => setCode(event.target.value.toUpperCase())}
          />
          <button type="submit" className="secondary">
            Open
          </button>
        </form>
      </div>
      {error ? <p className="error">{error}</p> : null}
      {waiting.length ? (
        <ul className="waiting-list">
          {waiting.map((item) => (
            <li key={item.id}>
              <button type="button" onClick={() => onSelect(item)}>
                <strong>{item.full_name || item.preferred_name || "Patient"}</strong>
                <span>
                  {item.code} · {minutesAgo(item.completed_at)}
                </span>
                {item.flags.some((f) => f.level === "alert") ? <em className="pill alert">Needs attention</em> : null}
              </button>
            </li>
          ))}
        </ul>
      ) : (
        <p className="quiet small">Patients who check in with Mia on the welcome screen appear here.</p>
      )}
    </section>
  );
}

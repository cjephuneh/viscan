"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { CoachPanel } from "@/components/coach-panel";
import { type CoachSession, type WorklistItem, getWorklist, listCoachSessions } from "@/lib/coach";
import { type Interpretation, getInterpretation, humanize, verdictLabel, verdictTone } from "@/lib/viscan";

function CaseSummary({ result }: { result: Interpretation }) {
  const tone = verdictTone(result.verdict.screening_verdict);
  return (
    <div className="case-summary">
      <div className={`verdict ${tone}`} data-coach="verdict">
        <p className="verdict-label">AI reading #{result.interpretation_id}</p>
        <p className="classification">{verdictLabel(result.verdict.screening_verdict)}</p>
        <p className="summary">{result.clinical_summary.rationale || result.diagnosis.summary}</p>
        <ul className="verdict-meta">
          <li>
            <span>VIA result</span>
            <strong>{humanize(result.verdict.via_result)}</strong>
          </li>
          <li>
            <span>Confidence</span>
            <strong>{Math.round(result.verdict.confidence * 100)}%</strong>
          </li>
          <li>
            <span>Risk index</span>
            <strong>{result.verdict.risk_score ?? "—"}</strong>
          </li>
          <li>
            <span>Swede</span>
            <strong>
              {result.swede.total}/{result.swede.max}
            </strong>
          </li>
        </ul>
      </div>
      <figure className="overlay" data-coach="overlay">
        <img src={result.links.overlay} alt="AI annotated screening image" />
      </figure>
      <section className="result-block" data-coach="findings">
        <h3 className="block-title">Findings</h3>
        <p>
          {humanize(result.findings?.acetowhite_density)} acetowhite · {humanize(result.findings?.lesion_margins)} margins ·{" "}
          {result.findings?.cervix_area_involved_percent ?? 0}% of the cervix · TZ{" "}
          {humanize(result.image_assessment.transformation_zone_type)} · SCJ{" "}
          {humanize(result.image_assessment.scj_visibility).toLowerCase()}
        </p>
      </section>
      {result.lesions.length ? (
        <section className="result-block" data-coach="lesions">
          <h3 className="block-title">Lesions</h3>
          <ul className="bullets">
            {result.lesions.map((l) => (
              <li key={l.id}>
                {l.clock_start}–{l.clock_end} o&apos;clock, {l.area_percent}%, {humanize(l.density).toLowerCase()}
              </li>
            ))}
          </ul>
        </section>
      ) : null}
      {result.treatment_eligibility.checklist.length ? (
        <section className="result-block" data-coach="eligibility">
          <h3 className="block-title">Ablation checklist</h3>
          <ul className="checklist">
            {result.treatment_eligibility.checklist.map((item) => (
              <li key={item.criterion} className={item.met ? "met" : item.met === null ? "unknown" : "unmet"}>
                <span aria-hidden="true">{item.met ? "✓" : item.met === null ? "?" : "✕"}</span>
                {item.criterion}
              </li>
            ))}
          </ul>
        </section>
      ) : null}
      {result.recommendation.flags.length ? (
        <section className="result-block" data-coach="flags">
          <h3 className="block-title">Flags</h3>
          <ul className="bullets flags">
            {result.recommendation.flags.map((f) => (
              <li key={f}>{f}</li>
            ))}
          </ul>
        </section>
      ) : null}
      <aside className="next-step" data-coach="next_step">
        <h3 className="block-title">Recommendation</h3>
        <p className="next-lead">{result.recommendation.action}</p>
      </aside>
      {result.clinical_summary.patient_explanation ? (
        <section className="result-block" data-coach="patient_explanation">
          <h3 className="block-title">What to tell the patient</h3>
          <p>{result.clinical_summary.patient_explanation}</p>
        </section>
      ) : null}
    </div>
  );
}

export function LearnScreen({ initialCaseId = null }: { initialCaseId?: number | null }) {
  const [cases, setCases] = useState<WorklistItem[]>([]);
  const [caseId, setCaseId] = useState<number | null>(initialCaseId);
  const [result, setResult] = useState<Interpretation | null>(null);
  const [clinicianId, setClinicianId] = useState("");
  const [record, setRecord] = useState<CoachSession[]>([]);

  useEffect(() => {
    getWorklist()
      .then(setCases)
      .catch(() => setCases([]));
  }, []);

  useEffect(() => {
    if (initialCaseId === null) return;
    let active = true;
    getInterpretation(initialCaseId)
      .then((r) => active && setResult(r))
      .catch(() => undefined);
    return () => {
      active = false;
    };
  }, [initialCaseId]);

  useEffect(() => {
    let active = true;
    listCoachSessions(clinicianId.trim() || undefined)
      .then((list) => active && setRecord(list.filter((s) => s.status === "completed").slice(0, 6)))
      .catch(() => undefined);
    return () => {
      active = false;
    };
  }, [clinicianId]);

  async function pick(id: number | null) {
    setCaseId(id);
    setResult(null);
    if (id !== null) setResult(await getInterpretation(id).catch(() => null));
  }

  return (
    <div className="page learn">
      <div className="atmosphere" aria-hidden="true" />
      <header className="learn-head">
        <div>
          <p className="brand-support">VISCAN training</p>
          <h1>Learn with Kezia</h1>
          <p className="hero-lede">
            An AI clinical coach who explains VIA results on real readings, shows you what to do next, quizzes you, and
            lets you rehearse telling patients their result.
          </p>
        </div>
        <nav className="screenings-nav">
          <Link href="/screening" className="back-link">
            ← Back to screening
          </Link>
          <Link href="/screenings" className="back-link">
            Past screenings →
          </Link>
        </nav>
      </header>

      <div className="learn-grid">
        <section className="learn-cases" aria-labelledby="cases-title">
          <label className="field">
            <span>Your clinician ID (for your training record)</span>
            <input value={clinicianId} onChange={(event) => setClinicianId(event.target.value)} placeholder="For example, nurse-07" />
          </label>

          <h2 id="cases-title" className="block-title">
            Choose what to learn from
          </h2>
          <div className="case-list">
            <button type="button" className={caseId === null ? "case-item on" : "case-item"} onClick={() => pick(null)}>
              <strong>Practice lesson</strong>
              <span>General VIA reading and management</span>
            </button>
            {cases.map((c) => (
              <button
                key={c.interpretation_id}
                type="button"
                className={caseId === c.interpretation_id ? "case-item on" : "case-item"}
                onClick={() => pick(c.interpretation_id)}
              >
                <strong>
                  <span className={`case-dot ${verdictTone(c.screening_verdict)}`} aria-hidden="true" />
                  Reading #{c.interpretation_id} · {verdictLabel(c.screening_verdict)}
                </strong>
                <span>
                  {humanize(c.via_result)} · risk {c.risk_score ?? "—"}
                  {c.patient_external_id ? ` · ${c.patient_external_id}` : ""}
                </span>
              </button>
            ))}
          </div>

          {result ? <CaseSummary result={result} /> : null}

          {record.length ? (
            <section className="training-record" aria-labelledby="record-title">
              <h2 id="record-title" className="block-title">
                Training record
              </h2>
              <ul>
                {record.map((s) => (
                  <li key={s.id}>
                    <strong>{s.interpretation_id ? `Reading #${s.interpretation_id}` : "Practice lesson"}</strong>
                    <span>
                      {s.score.answered ? `Quiz ${s.score.correct}/${s.score.answered}` : "No quiz"}
                      {s.topics.length ? ` · ${s.topics.map((t) => t.topic).join(", ")}` : ""}
                    </span>
                  </li>
                ))}
              </ul>
            </section>
          ) : null}
        </section>

        <CoachPanel key={caseId ?? "practice"} interpretation={result} clinicianId={clinicianId.trim()} variant="page" />
      </div>
    </div>
  );
}

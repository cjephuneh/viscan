"use client";

import Link from "next/link";
import { useEffect, useId, useRef, useState } from "react";
import { CoachPanel } from "@/components/coach-panel";
import { CheckedInPatients, IntakeSummary } from "@/components/intake-panel";
import { SendResults } from "@/components/send-results";
import { VideoReport } from "@/components/video-report";
import { ViscanMark } from "@/components/viscan-mark";
import { type Intake, getIntake } from "@/lib/intake";
import {
  type Interpretation,
  type ViaResult,
  type VisitDetails,
  confirmReading,
  humanize,
  interpretImage,
  verdictLabel,
  verdictTone,
  viaToVerdict,
} from "@/lib/viscan";

type Phase = "empty" | "ready" | "reading" | "result" | "confirmed";

const READING_STEPS = [
  "Image uploaded",
  "Checking image quality",
  "AI reading the VIA image",
  "Applying WHO screening rules",
];

const FLOW_STEPS = ["Image obtained", "Interpretation", "Clinician confirms"];
const ACCEPTED = ["image/jpeg", "image/png", "image/webp"];
const MAX_BYTES = 10 * 1024 * 1024;

const SYMPTOMS: { id: string; label: string }[] = [
  { id: "postcoital_bleeding", label: "Bleeding after sex" },
  { id: "intermenstrual_bleeding", label: "Bleeding between periods" },
  { id: "postmenopausal_bleeding", label: "Bleeding after menopause" },
  { id: "abnormal_discharge", label: "Abnormal discharge" },
  { id: "pelvic_pain", label: "Pelvic pain" },
  { id: "dyspareunia", label: "Pain during sex" },
];

const EMPTY_VISIT: VisitDetails = {
  patientId: "",
  age: "",
  hivStatus: "unknown",
  hpvStatus: "unknown",
  pregnant: "",
  previouslyTreated: "",
  smoker: "",
  parity: "",
  symptoms: [],
  site: "",
  clinicianId: "",
};

function formatSize(bytes: number) {
  if (bytes < 1024 * 1024) return `${Math.max(1, Math.round(bytes / 1024))} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

function clockText(positions: number[] | undefined) {
  if (!positions?.length) return "None";
  return `${positions.join(", ")} o'clock`;
}

function otherFinding(via: ViaResult): ViaResult | null {
  if (via === "VIA_POSITIVE" || via === "SUSPICIOUS_FOR_CANCER") return "VIA_NEGATIVE";
  if (via === "VIA_NEGATIVE") return "VIA_POSITIVE";
  return null;
}

function SelectField({
  label,
  value,
  onChange,
  options,
}: {
  label: string;
  value: string;
  onChange: (value: string) => void;
  options: [string, string][];
}) {
  return (
    <label className="field">
      <span>{label}</span>
      <select value={value} onChange={(event) => onChange(event.target.value)}>
        {options.map(([v, text]) => (
          <option key={v} value={v}>
            {text}
          </option>
        ))}
      </select>
    </label>
  );
}

const YES_NO: [string, string][] = [
  ["", "Unknown"],
  ["false", "No"],
  ["true", "Yes"],
];
const TEST_STATUS: [string, string][] = [
  ["unknown", "Unknown / not done"],
  ["negative", "Negative"],
  ["positive", "Positive"],
];

const tri = (value: boolean | null | undefined) => (value === null || value === undefined ? "" : String(value));

function visitFromIntake(intake: Intake, current: VisitDetails): VisitDetails {
  const p = intake.prefill;
  return {
    ...current,
    patientId: p.patient_external_id,
    age: p.age?.toString() ?? "",
    hivStatus: p.hiv_status || "unknown",
    pregnant: tri(p.pregnant),
    previouslyTreated: tri(p.previously_treated),
    smoker: tri(p.smoker),
    parity: p.parity?.toString() ?? "",
    symptoms: p.symptoms.filter((s) => SYMPTOMS.some((known) => known.id === s)),
  };
}

export function ScreeningScreen({ intakeId }: { intakeId?: string } = {}) {
  const inputId = useId();
  const inputRef = useRef<HTMLInputElement>(null);
  const beforeInputId = useId();
  const beforeInputRef = useRef<HTMLInputElement>(null);
  const previewRef = useRef<string | null>(null);
  const patientRef = useRef<HTMLInputElement>(null);
  const clinicianRef = useRef<HTMLInputElement>(null);
  const uploadRef = useRef<HTMLElement | null>(null);
  const dragDepth = useRef(0);

  const [visit, setVisit] = useState<VisitDetails>(EMPTY_VISIT);
  const [patientError, setPatientError] = useState("");
  const [clinicianError, setClinicianError] = useState("");
  const [file, setFile] = useState<File | null>(null);
  const [previewUrl, setPreviewUrl] = useState<string | null>(null);
  // Optional baseline frame taken before acetic acid; stored with the visit and
  // shown to the model next to the VIA frame. Never read on its own.
  const [beforeFile, setBeforeFile] = useState<File | null>(null);
  const [beforePreviewUrl, setBeforePreviewUrl] = useState<string | null>(null);
  const [error, setError] = useState("");
  const [hot, setHot] = useState(false);
  const [phase, setPhase] = useState<Phase>("empty");
  const [step, setStep] = useState(0);
  const [elapsed, setElapsed] = useState(0);
  const [result, setResult] = useState<Interpretation | null>(null);
  const [apiError, setApiError] = useState("");
  const [notes, setNotes] = useState("");
  const [finalVia, setFinalVia] = useState<ViaResult | null>(null);
  const [confirming, setConfirming] = useState(false);
  const [intake, setIntake] = useState<Intake | null>(null);
  const [coachOpen, setCoachOpen] = useState(false);

  function selectIntake(next: Intake | null) {
    setIntake(next);
    setPatientError("");
    setVisit((current) =>
      next ? visitFromIntake(next, current) : { ...EMPTY_VISIT, site: current.site, clinicianId: current.clinicianId },
    );
  }

  useEffect(() => {
    if (!intakeId) return;
    let active = true;
    getIntake(intakeId)
      .then((found) => {
        if (!active) return;
        setIntake(found);
        setVisit((current) => visitFromIntake(found, current));
      })
      .catch(() => undefined);
    return () => {
      active = false;
    };
  }, [intakeId]);

  const update = <K extends keyof VisitDetails>(key: K, value: VisitDetails[K]) =>
    setVisit((current) => ({ ...current, [key]: value }));

  useEffect(() => {
    previewRef.current = previewUrl;
  }, [previewUrl]);

  useEffect(() => {
    return () => {
      if (previewRef.current) URL.revokeObjectURL(previewRef.current);
    };
  }, []);

  useEffect(() => {
    if (phase !== "reading") return;
    const timers = [
      window.setTimeout(() => setStep(1), 800),
      window.setTimeout(() => setStep(2), 2500),
      window.setTimeout(() => setStep(3), 25000),
    ];
    const ticker = window.setInterval(() => setElapsed((s) => s + 1), 1000);
    return () => {
      timers.forEach((timer) => window.clearTimeout(timer));
      window.clearInterval(ticker);
    };
  }, [phase]);

  function takeFile(next: File | undefined) {
    if (!validImage(next)) return;
    setError("");
    setApiError("");
    setNotes("");
    setFinalVia(null);
    setResult(null);
    if (previewUrl) URL.revokeObjectURL(previewUrl);
    setPreviewUrl(URL.createObjectURL(next));
    setFile(next);
    setPhase("ready");
  }

  function validImage(next: File | undefined): next is File {
    if (!next) return false;
    if (!ACCEPTED.includes(next.type)) {
      setError("Use a JPG, PNG, or WEBP image.");
      return false;
    }
    if (next.size > MAX_BYTES) {
      setError("That image is larger than 10 MB. Choose a smaller one.");
      return false;
    }
    return true;
  }

  function takeBefore(next: File | undefined) {
    if (!validImage(next)) return;
    setError("");
    if (beforePreviewUrl) URL.revokeObjectURL(beforePreviewUrl);
    setBeforePreviewUrl(URL.createObjectURL(next));
    setBeforeFile(next);
    // A different baseline means a different reading: go back to "ready".
    if (result) {
      setResult(null);
      setFinalVia(null);
      setPhase(file ? "ready" : "empty");
    }
  }

  function clearBefore() {
    if (beforePreviewUrl) URL.revokeObjectURL(beforePreviewUrl);
    setBeforePreviewUrl(null);
    setBeforeFile(null);
    if (beforeInputRef.current) beforeInputRef.current.value = "";
    if (result) {
      setResult(null);
      setFinalVia(null);
      setPhase(file ? "ready" : "empty");
    }
  }

  function onDrop(event: React.DragEvent) {
    event.preventDefault();
    dragDepth.current = 0;
    setHot(false);
    takeFile(event.dataTransfer.files?.[0]);
  }

  function clearImage() {
    setCoachOpen(false);
    if (previewUrl) URL.revokeObjectURL(previewUrl);
    setPreviewUrl(null);
    setFile(null);
    if (beforePreviewUrl) URL.revokeObjectURL(beforePreviewUrl);
    setBeforePreviewUrl(null);
    setBeforeFile(null);
    if (beforeInputRef.current) beforeInputRef.current.value = "";
    setPhase("empty");
    setResult(null);
    setFinalVia(null);
    setNotes("");
    setError("");
    setApiError("");
    if (inputRef.current) inputRef.current.value = "";
  }

  function startOver() {
    clearImage();
    selectIntake(null);
  }

  async function runReading() {
    if (!file) return;
    if (!visit.patientId.trim()) {
      setPatientError("Add the patient ID before reading the image.");
      patientRef.current?.focus();
      return;
    }
    setPatientError("");
    setApiError("");
    setStep(0);
    setElapsed(0);
    setPhase("reading");
    try {
      const data = await interpretImage(file, visit, intake?.id, beforeFile);
      setResult(data);
      setPhase("result");
    } catch (err) {
      setApiError((err as Error).message);
      setPhase("ready");
    }
  }

  async function confirm(via: ViaResult) {
    if (!result) return;
    if (!visit.clinicianId.trim()) {
      setClinicianError("Add your clinician ID before confirming.");
      clinicianRef.current?.focus();
      return;
    }
    setClinicianError("");
    setConfirming(true);
    setApiError("");
    try {
      await confirmReading(result.interpretation_id, {
        clinician_id: visit.clinicianId.trim(),
        via_result: via,
        notes: notes.trim() || undefined,
      });
      setFinalVia(via);
      setPhase("confirmed");
    } catch (err) {
      setApiError((err as Error).message);
    } finally {
      setConfirming(false);
    }
  }

  function focusUpload() {
    uploadRef.current?.scrollIntoView({ behavior: "smooth", block: "start" });
    inputRef.current?.focus();
  }

  const imageReady = Boolean(previewUrl);
  const shownVerdict = finalVia ? viaToVerdict(finalVia) : result?.verdict.screening_verdict;
  const tone = verdictTone(shownVerdict);
  const other = result ? otherFinding(result.verdict.via_result) : null;
  const finalSuspicious = finalVia === "VIA_POSITIVE" || finalVia === "SUSPICIOUS_FOR_CANCER";

  const stepState = (index: number) => {
    if (index === 0) return imageReady ? "done" : "active";
    if (index === 1)
      return phase === "reading" ? "active" : phase === "result" || phase === "confirmed" ? "done" : "";
    if (index === 2) return phase === "confirmed" ? "done" : phase === "result" ? "active" : "";
    return "";
  };

  const panelStatus =
    phase === "confirmed"
      ? "Confirmed"
      : phase === "reading"
        ? "Reading in progress"
        : phase === "result"
          ? "Awaiting your confirmation"
          : phase === "ready"
            ? "Ready to read"
            : "Waiting for an image";

  return (
    <div className={coachOpen && result ? "page with-coach" : "page"}>
      <div className="atmosphere" aria-hidden="true" />

      <header className="hero">
        <div className="hero-copy">
          <p className="brand-support">Supports VIA cervical screening</p>
          <h1 className="brand-name">New screening</h1>
          <p className="hero-lede">
            Place the screening image from the visit, review a reading, and confirm it yourself
            before anything is treated as final.
          </p>
          <div className="hero-actions">
            <button type="button" className="choose" onClick={focusUpload}>
              Start with an image
            </button>
            <p className="hero-note">AI-assisted reading · clinician confirms every result</p>
          </div>
        </div>

        <aside className="hero-aside">
          <ol className="flow">
            {FLOW_STEPS.map((label, index) => (
              <li key={label} className={stepState(index)}>
                <span className="flow-index">0{index + 1}</span>
                <span className="flow-label">{label}</span>
              </li>
            ))}
          </ol>
          <p className="aside-note">
            The AI reading is decision support. Nothing is final until you confirm it.
          </p>
        </aside>
      </header>

      {intake ? <IntakeSummary intake={intake} onClear={() => selectIntake(null)} /> : <CheckedInPatients onSelect={selectIntake} />}

      <section className="session visit" aria-label="Visit details">
        <div className="visit-grid">
          <div className="field patient-field">
            <label htmlFor="patient-id">
              <span>Patient ID</span>
            </label>
            <input
              id="patient-id"
              ref={patientRef}
              value={visit.patientId}
              onChange={(event) => {
                update("patientId", event.target.value);
                if (event.target.value.trim()) setPatientError("");
              }}
              placeholder="For example, PT-1042"
              aria-invalid={Boolean(patientError)}
              aria-describedby={patientError ? "patient-error" : "patient-hint"}
            />
            {patientError ? (
              <small id="patient-error">{patientError}</small>
            ) : (
              <small id="patient-hint">Required before the reading</small>
            )}
          </div>
          <label className="field">
            <span>Age</span>
            <input
              type="number"
              min={10}
              max={100}
              value={visit.age}
              onChange={(event) => update("age", event.target.value)}
              placeholder="Years"
            />
          </label>
          <SelectField label="HIV status" value={visit.hivStatus} onChange={(v) => update("hivStatus", v)} options={TEST_STATUS} />
          <SelectField label="HPV test" value={visit.hpvStatus} onChange={(v) => update("hpvStatus", v)} options={TEST_STATUS} />
          <SelectField label="Pregnant" value={visit.pregnant} onChange={(v) => update("pregnant", v)} options={YES_NO} />
          <SelectField
            label="Treated before"
            value={visit.previouslyTreated}
            onChange={(v) => update("previouslyTreated", v)}
            options={YES_NO}
          />
          <SelectField label="Smoker" value={visit.smoker} onChange={(v) => update("smoker", v)} options={YES_NO} />
          <label className="field">
            <span>Births (parity)</span>
            <input
              type="number"
              min={0}
              max={25}
              value={visit.parity}
              onChange={(event) => update("parity", event.target.value)}
            />
          </label>
          <label className="field">
            <span>Screening site</span>
            <input value={visit.site} onChange={(event) => update("site", event.target.value)} placeholder="Clinic name" />
          </label>
          <div className="field">
            <label htmlFor="clinician-id">
              <span>Clinician ID</span>
            </label>
            <input
              id="clinician-id"
              ref={clinicianRef}
              value={visit.clinicianId}
              onChange={(event) => {
                update("clinicianId", event.target.value);
                if (event.target.value.trim()) setClinicianError("");
              }}
              placeholder="For example, nurse-07"
              aria-invalid={Boolean(clinicianError)}
              aria-describedby={clinicianError ? "clinician-error" : undefined}
            />
            {clinicianError ? <small id="clinician-error">{clinicianError}</small> : null}
          </div>
        </div>
        <fieldset className="symptoms">
          <legend>Symptoms reported</legend>
          {SYMPTOMS.map((symptom) => (
            <label key={symptom.id} className="chip">
              <input
                type="checkbox"
                checked={visit.symptoms.includes(symptom.id)}
                onChange={(event) =>
                  update(
                    "symptoms",
                    event.target.checked
                      ? [...visit.symptoms, symptom.id]
                      : visit.symptoms.filter((s) => s !== symptom.id),
                  )
                }
              />
              <span>{symptom.label}</span>
            </label>
          ))}
        </fieldset>
      </section>

      <main className="stage">
        <section ref={uploadRef} className="panel" aria-labelledby="capture-title" tabIndex={-1}>
          <div className="panel-head">
            <div>
              <p className="eyebrow">Capture</p>
              <h2 id="capture-title">Screening image</h2>
            </div>
            <p className="panel-status">{imageReady ? "Ready for review" : "Waiting for a capture"}</p>
          </div>

          <input
            id={inputId}
            ref={inputRef}
            type="file"
            accept="image/jpeg,image/png,image/webp"
            hidden
            onChange={(event) => takeFile(event.target.files?.[0])}
          />

          {previewUrl ? (
            <div className="frame">
              <img src={previewUrl} alt="Screening image selected for this visit" />
              <div className="frame-meta">
                <p>
                  <strong>{file?.name}</strong>
                  <span>{file ? formatSize(file.size) : ""}</span>
                </p>
                <div className="frame-actions">
                  <button type="button" onClick={() => inputRef.current?.click()} disabled={phase === "reading"}>
                    Replace
                  </button>
                  <button type="button" onClick={clearImage} disabled={phase === "reading"}>
                    Remove
                  </button>
                </div>
              </div>
            </div>
          ) : (
            <div
              className={hot ? "dropzone hot" : "dropzone"}
              onDragEnter={(event) => {
                event.preventDefault();
                dragDepth.current += 1;
                setHot(true);
              }}
              onDragOver={(event) => event.preventDefault()}
              onDragLeave={() => {
                dragDepth.current -= 1;
                if (dragDepth.current <= 0) {
                  dragDepth.current = 0;
                  setHot(false);
                }
              }}
              onDrop={onDrop}
            >
              <div className="aperture" aria-hidden="true">
                <ViscanMark />
              </div>
              <h3>Place the screening image</h3>
              <p>White-light photo about one minute after acetic acid. Drop it here or choose it.</p>
              <button type="button" className="choose" onClick={() => inputRef.current?.click()}>
                Choose image
              </button>
              <p className="formats">JPG, PNG, WEBP · up to 10 MB</p>
            </div>
          )}
          <input
            id={beforeInputId}
            ref={beforeInputRef}
            type="file"
            accept="image/jpeg,image/png,image/webp"
            hidden
            onChange={(event) => takeBefore(event.target.files?.[0])}
          />
          <div className="before-slot" data-coach="before">
            {beforePreviewUrl ? (
              <>
                <img src={beforePreviewUrl} alt="Cervix before acetic acid" />
                <p>
                  <strong>Before acetic acid</strong>
                  <span>
                    {beforeFile?.name}
                    {beforeFile ? ` · ${formatSize(beforeFile.size)}` : ""}
                  </span>
                </p>
                <div className="frame-actions">
                  <button type="button" onClick={() => beforeInputRef.current?.click()} disabled={phase === "reading"}>
                    Replace
                  </button>
                  <button type="button" onClick={clearBefore} disabled={phase === "reading"}>
                    Remove
                  </button>
                </div>
              </>
            ) : (
              <>
                <p>
                  <strong>Before acetic acid</strong>
                  <span>Optional. Gives the AI a baseline so only true acetowhite change is counted.</span>
                </p>
                <button
                  type="button"
                  className="choose small"
                  onClick={() => beforeInputRef.current?.click()}
                  disabled={phase === "reading"}
                >
                  Add before image
                </button>
              </>
            )}
          </div>
          {error ? <p className="error">{error}</p> : null}

          {result && (phase === "result" || phase === "confirmed") ? (
            <div className={result.links.image_before ? "overlays pair" : "overlays"}>
              {result.links.image_before ? (
                <figure className="overlay">
                  <img src={result.links.image_before} alt="Cervix before acetic acid" />
                  <figcaption>Before acetic acid (baseline)</figcaption>
                </figure>
              ) : null}
              <figure className="overlay" data-coach="overlay">
                <img src={result.links.overlay} alt="AI annotated screening image with lesion markers" />
                <figcaption>{result.links.image_before ? "After acetic acid · " : ""}AI lesion markers are approximate.</figcaption>
              </figure>
            </div>
          ) : null}
        </section>

        <section className="panel result-panel" aria-labelledby="result-title" aria-live="polite">
          <div className="panel-head">
            <div>
              <p className="eyebrow">Reading</p>
              <h2 id="result-title">Interpretation</h2>
            </div>
            <p className="panel-status">{panelStatus}</p>
          </div>

          {phase === "empty" ? (
            <div className="empty-result">
              <div className="reading-slot">
                <p className="slot-label">AI reading</p>
                <p className="slot-title">The reading will appear here</p>
                <p className="summary">
                  Add the visit details and a screening image. VISCAN reads it and tells you whether it is
                  suspicious or not suspicious, then you confirm it yourself.
                </p>
              </div>
              <ul className="outcome-preview" aria-label="Possible readings">
                <li className="outcome-preview-item alert">
                  <span className="outcome-swatch" aria-hidden="true" />
                  <div>
                    <strong>Suspicious</strong>
                    <span>Referral and pharmacy options if you agree</span>
                  </div>
                </li>
                <li className="outcome-preview-item clear">
                  <span className="outcome-swatch" aria-hidden="true" />
                  <div>
                    <strong>Not suspicious</strong>
                    <span>Routine follow-up if you agree</span>
                  </div>
                </li>
              </ul>
              <p className="empty-foot">Nothing is final until a clinician confirms the finding.</p>
            </div>
          ) : null}

          {phase === "ready" ? (
            <div className="empty-result">
              <div className="reading-slot active">
                <p className="slot-label">AI reading</p>
                <p className="slot-title">Ready to read this image</p>
                <p className="summary">
                  Check the visit details, then start the reading. It usually takes 30 to 60 seconds.
                </p>
              </div>
              {apiError ? <p className="error">{apiError}</p> : null}
              <div className="actions">
                <button type="button" className="primary" onClick={runReading}>
                  Read this image
                </button>
              </div>
            </div>
          ) : null}

          {phase === "reading" ? (
            <div className="reading">
              <div className="reading-slot active">
                <p className="slot-label">AI reading</p>
                <p className="slot-title">Preparing the reading</p>
                <p className="quiet">
                  VISCAN is reading the image against the VIA checklist. {elapsed}s elapsed.
                </p>
              </div>
              <ol className="timeline">
                {READING_STEPS.map((label, index) => (
                  <li key={label} className={index < step ? "past" : index === step ? "now" : ""}>
                    <span className="dot" />
                    <span>{label}</span>
                  </li>
                ))}
              </ol>
            </div>
          ) : null}

          {result && (phase === "result" || phase === "confirmed") ? (
            <div className={`result is-${tone}`}>
              {phase === "confirmed" ? (
                <p className="seal">
                  <span className="seal-mark" aria-hidden="true" />
                  Confirmed by clinician
                </p>
              ) : null}

              <div className={`verdict ${tone}`} data-coach="verdict">
                <p className="verdict-label">
                  {phase === "confirmed" ? "Confirmed result" : "AI reading · awaiting your confirmation"}
                </p>
                <p className="classification">{verdictLabel(shownVerdict)}</p>
                <p className="summary">{result.clinical_summary.rationale || result.diagnosis.summary}</p>
                <ul className="verdict-meta" aria-label="Reading details">
                  <li>
                    <span>VIA result</span>
                    <strong>{humanize(finalVia ?? result.verdict.via_result)}</strong>
                  </li>
                  <li>
                    <span>AI confidence</span>
                    <strong>{Math.round(result.verdict.confidence * 100)}%</strong>
                  </li>
                  <li>
                    <span>Risk index</span>
                    <strong>
                      {result.verdict.risk_score ?? "—"} · {humanize(result.verdict.suspicion_level)}
                    </strong>
                  </li>
                  <li>
                    <span>Urgency</span>
                    <strong>{humanize(result.diagnosis.urgency)}</strong>
                  </li>
                </ul>
              </div>

              {!coachOpen ? (
                <button type="button" className="coach-invite" onClick={() => setCoachOpen(true)}>
                  <span className="coach-invite-dot" aria-hidden="true" />
                  <span>
                    <strong>Walk me through this with Kezia</strong>
                    <small>AI clinical coach · explains the result, the next steps, quizzes you</small>
                  </span>
                </button>
              ) : null}

              <section className="result-block" aria-labelledby="findings-heading" data-coach="findings">
                <h3 id="findings-heading" className="block-title">
                  Findings
                </h3>
                <dl className="findings">
                  <div>
                    <dt>Acetowhite change</dt>
                    <dd>
                      {humanize(result.findings?.acetowhite_density)}
                      {result.findings?.lesion_margins && result.findings?.lesion_margins !== "none"
                        ? ` · ${humanize(result.findings?.lesion_margins)} margins`
                        : ""}
                    </dd>
                  </div>
                  <div>
                    <dt>Lesion location</dt>
                    <dd>{clockText(result.findings?.lesion_clock_positions)}</dd>
                  </div>
                  <div>
                    <dt>Cervix involved</dt>
                    <dd>
                      {result.findings?.cervix_area_involved_percent ?? 0}%
                      {result.findings?.extends_into_canal ? " · extends into canal" : ""}
                    </dd>
                  </div>
                  <div>
                    <dt>Transformation zone</dt>
                    <dd>
                      {humanize(result.image_assessment.transformation_zone_type)} · SCJ{" "}
                      {humanize(result.image_assessment.scj_visibility).toLowerCase()}
                    </dd>
                  </div>
                  <div>
                    <dt>Image type</dt>
                    <dd>{humanize(result.image_assessment.image_modality)}</dd>
                  </div>
                  <div>
                    <dt>Swede score</dt>
                    <dd>
                      {result.swede.total}/{result.swede.max} · {result.swede.interpretation}
                    </dd>
                  </div>
                  <div>
                    <dt>Ablation eligible</dt>
                    <dd>
                      {result.recommendation.ablation_eligible === null
                        ? "Not applicable"
                        : result.recommendation.ablation_eligible
                          ? "Yes"
                          : "No"}
                    </dd>
                  </div>
                  <div>
                    <dt>Follow-up due</dt>
                    <dd>{result.follow_up_due ?? "—"}</dd>
                  </div>
                </dl>
              </section>

              {result.lesions.length ? (
                <section className="result-block" aria-labelledby="lesions-heading" data-coach="lesions">
                  <h3 id="lesions-heading" className="block-title">
                    Lesions ({result.lesions.length})
                  </h3>
                  <ol className="lesion-list">
                    {result.lesions.map((lesion) => (
                      <li key={lesion.id}>
                        <strong>
                          {lesion.clock_start}–{lesion.clock_end} o&apos;clock · {lesion.area_percent}%
                        </strong>
                        <span>
                          {humanize(lesion.density)}, {humanize(lesion.margins).toLowerCase()} margins,{" "}
                          {humanize(lesion.vessel_pattern).toLowerCase()}
                          {lesion.touches_scj ? ", touches SCJ" : ""}
                        </span>
                      </li>
                    ))}
                  </ol>
                </section>
              ) : null}

              {result.clinical_summary.key_observations.length ? (
                <section className="result-block" aria-labelledby="obs-heading" data-coach="observations">
                  <h3 id="obs-heading" className="block-title">
                    Key observations
                  </h3>
                  <ul className="bullets">
                    {result.clinical_summary.key_observations.map((item) => (
                      <li key={item}>{item}</li>
                    ))}
                  </ul>
                </section>
              ) : null}

              {result.histology_likelihood ? (
                <section className="result-block" aria-labelledby="histo-heading" data-coach="histology">
                  <h3 id="histo-heading" className="block-title">
                    AI-estimated histology likelihood
                  </h3>
                  <ul className="bars">
                    {Object.entries(result.histology_likelihood).map(([key, value]) => (
                      <li key={key}>
                        <span>{humanize(key)}</span>
                        <span className="bar" aria-hidden="true">
                          <span style={{ width: `${Math.round(value * 100)}%` }} />
                        </span>
                        <strong>{Math.round(value * 100)}%</strong>
                      </li>
                    ))}
                  </ul>
                </section>
              ) : null}

              {result.treatment_eligibility.checklist.length ? (
                <section className="result-block" aria-labelledby="elig-heading" data-coach="eligibility">
                  <h3 id="elig-heading" className="block-title">
                    WHO ablation checklist
                  </h3>
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

              {result.recommendation.flags.length || result.image_assessment.adequacy.issues.length ? (
                <section className="result-block" aria-labelledby="flags-heading" data-coach="flags">
                  <h3 id="flags-heading" className="block-title">
                    Flags
                  </h3>
                  <ul className="bullets flags">
                    {[...new Set([...result.image_assessment.adequacy.issues, ...result.recommendation.flags])].map((flag) => (
                      <li key={flag}>{flag}</li>
                    ))}
                  </ul>
                </section>
              ) : null}

              {result.clinical_summary.patient_explanation ? (
                <section className="result-block" aria-labelledby="explain-heading" data-coach="patient_explanation">
                  <h3 id="explain-heading" className="block-title">
                    What to tell the patient
                  </h3>
                  <p className="summary">{result.clinical_summary.patient_explanation}</p>
                </section>
              ) : null}

              {phase === "result" ? (
                <>
                  <label className="field notes-field">
                    <span className="note-label">Clinical notes</span>
                    <textarea
                      className="notes"
                      value={notes}
                      onChange={(event) => setNotes(event.target.value)}
                      placeholder="What you saw during the visit"
                    />
                  </label>

                  <aside className="next-step" aria-labelledby="next-heading" data-coach="next_step">
                    <h3 id="next-heading" className="block-title">
                      If you confirm
                    </h3>
                    <p className="next-lead">{result.recommendation.action}</p>
                    {result.verdict.is_suspicious ? (
                      <p className="follow">
                        After you confirm, you can refer the patient to a partner hospital, find nearby
                        pharmacies, and send the result by SMS or WhatsApp.
                      </p>
                    ) : (
                      <p className="follow">
                        After you confirm, you can send the result to the patient by SMS or WhatsApp.
                      </p>
                    )}
                  </aside>

                  {clinicianError ? <p className="error">{clinicianError}</p> : null}
                  {apiError ? <p className="error">{apiError}</p> : null}

                  <div className="actions">
                    <button
                      type="button"
                      className="primary"
                      disabled={confirming}
                      onClick={() => confirm(result.verdict.via_result)}
                    >
                      Confirm this finding
                    </button>
                    {other ? (
                      <button type="button" className="secondary" disabled={confirming} onClick={() => confirm(other)}>
                        Record the other finding
                      </button>
                    ) : null}
                    <button type="button" className="ghost" onClick={clearImage}>
                      Retake
                    </button>
                  </div>
                </>
              ) : (
                <>
                  <article className="record" data-coach="record">
                    <div className="record-head">
                      <h3>Digital record</h3>
                      <p className="record-note">Saved for this visit after clinician confirmation</p>
                    </div>
                    <dl>
                      <div>
                        <dt>Patient ID</dt>
                        <dd>{visit.patientId.trim()}</dd>
                      </div>
                      <div>
                        <dt>Result</dt>
                        <dd className={`record-result ${tone}`}>{verdictLabel(shownVerdict)}</dd>
                      </div>
                      <div>
                        <dt>Confirmed by</dt>
                        <dd>{visit.clinicianId.trim()}</dd>
                      </div>
                      <div className="record-image-row">
                        <dt>Image</dt>
                        <dd>
                          <div className="record-image">
                            {beforePreviewUrl ? <img src={beforePreviewUrl} alt="" /> : null}
                            {previewUrl ? <img src={previewUrl} alt="" /> : null}
                            <span>
                              {beforeFile ? `${beforeFile.name} (before) · ` : ""}
                              {file?.name}
                            </span>
                          </div>
                        </dd>
                      </div>
                      <div>
                        <dt>Clinical notes</dt>
                        <dd>{notes.trim() || "None added"}</dd>
                      </div>
                      <div>
                        <dt>Follow-up</dt>
                        <dd>
                          {finalSuspicious
                            ? result.recommendation.action
                            : `Routine follow-up${result.follow_up_due ? ` by ${result.follow_up_due}` : ""}.`}
                        </dd>
                      </div>
                    </dl>
                    <div className="actions">
                      {finalSuspicious ? (
                        <Link className="primary link-button" href={`/care/${result.interpretation_id}`}>
                          Refer &amp; find pharmacies
                        </Link>
                      ) : null}
                      <a className="secondary link-button" href={result.links.report} target="_blank" rel="noreferrer">
                        Open printable report
                      </a>
                      <button type="button" className="ghost" onClick={startOver}>
                        Start another screening
                      </button>
                    </div>
                  </article>

                  <VideoReport interpretationId={result.interpretation_id} />

                  <SendResults
                    interpretationId={result.interpretation_id}
                    sentBy={visit.clinicianId.trim()}
                    defaultPhone={intake?.prefill.phone}
                    defaultChannel={intake?.prefill.result_channel === "none" ? null : intake?.prefill.result_channel}
                  />
                </>
              )}
            </div>
          ) : null}

          <p className="footnote">
            {result
              ? `Engine: ${result.engine.model} · ${(result.engine.latency_ms / 1000).toFixed(0)} s. ${result.disclaimer}`
              : "AI readings are decision support. A result is not final until you confirm it."}
          </p>
        </section>
      </main>

      {coachOpen && result ? (
        <CoachPanel
          key={result.interpretation_id}
          interpretation={result}
          clinicianId={visit.clinicianId.trim()}
          onClose={() => setCoachOpen(false)}
        />
      ) : null}
    </div>
  );
}

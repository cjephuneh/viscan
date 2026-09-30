"use client";

import { useEffect, useId, useRef, useState } from "react";

type Outcome = "suspicious" | "clear";
type Phase = "empty" | "reading" | "result" | "confirmed";

type Sample = {
  label: string;
  tone: Outcome;
  summary: string;
  findings: { label: string; value: string }[];
  followUp: string;
  recommendation: string;
};

const SAMPLES: Record<Outcome, Sample> = {
  suspicious: {
    label: "Suspicious",
    tone: "suspicious",
    summary:
      "The sample reading flags acetowhite change that should be reviewed before this visit ends.",
    findings: [
      { label: "Acetowhite change", value: "Present in the sample reading" },
      { label: "Borders", value: "Need a closer look" },
      { label: "Protocol", value: "VIA checklist attached to this image" },
    ],
    followUp:
      "If you confirm this, the next step is a referral to a partner hospital. The avatar can explain that to the patient, and the result can go out by SMS or WhatsApp.",
    recommendation: "Refer to a partner hospital if you agree with this reading.",
  },
  clear: {
    label: "Not suspicious",
    tone: "clear",
    summary:
      "The sample reading does not flag a suspicious acetowhite change. Routine follow-up still belongs with you.",
    findings: [
      { label: "Acetowhite change", value: "Not flagged in the sample reading" },
      { label: "Borders", value: "No suspicious border called" },
      { label: "Protocol", value: "VIA checklist attached to this image" },
    ],
    followUp:
      "If you confirm this, routine follow-up is the recommendation. The avatar can explain the next visit, and the result can go out by SMS or WhatsApp.",
    recommendation: "Routine follow-up. No referral from this reading.",
  },
};

const READING_STEPS = [
  "Image obtained",
  "Applying the VIA checklist",
  "Preparing the reading",
];

const FLOW_STEPS = ["Image obtained", "Interpretation", "Clinician confirms"];

const ACCEPTED = ["image/jpeg", "image/png", "image/webp"];

function formatSize(bytes: number) {
  if (bytes < 1024 * 1024) return `${Math.max(1, Math.round(bytes / 1024))} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

function ViscanMark({ className }: { className?: string }) {
  return (
    <svg className={className} viewBox="0 0 32 32" fill="none" aria-hidden="true">
      <circle cx="16" cy="16" r="9" stroke="currentColor" strokeWidth="1.6" />
      <circle cx="16" cy="16" r="2.3" fill="currentColor" />
      <path
        d="M16 4.5v3.2M16 24.3v3.2M4.5 16h3.2M24.3 16h3.2"
        stroke="currentColor"
        strokeWidth="1.4"
        strokeLinecap="round"
      />
    </svg>
  );
}

export function ScreeningScreen() {
  const inputId = useId();
  const inputRef = useRef<HTMLInputElement>(null);
  const previewRef = useRef<string | null>(null);
  const patientRef = useRef<HTMLInputElement>(null);
  const uploadRef = useRef<HTMLElement | null>(null);

  const [patientId, setPatientId] = useState("");
  const [patientError, setPatientError] = useState("");
  const [fileName, setFileName] = useState("");
  const [fileSize, setFileSize] = useState("");
  const [previewUrl, setPreviewUrl] = useState<string | null>(null);
  const [error, setError] = useState("");
  const [hot, setHot] = useState(false);
  const dragDepth = useRef(0);
  const [phase, setPhase] = useState<Phase>("empty");
  const [step, setStep] = useState(0);
  const [outcome, setOutcome] = useState<Outcome>("suspicious");
  const [notes, setNotes] = useState("");
  const [finalOutcome, setFinalOutcome] = useState<Outcome | null>(null);

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
    setStep(0);
    const timers = [
      window.setTimeout(() => setStep(1), 650),
      window.setTimeout(() => setStep(2), 1300),
      window.setTimeout(() => setPhase("result"), 2000),
    ];
    return () => timers.forEach((timer) => window.clearTimeout(timer));
  }, [phase, fileName]);

  function takeFile(file: File | undefined) {
    if (!file) return;
    if (!ACCEPTED.includes(file.type)) {
      setError("Use a JPG, PNG, or WEBP image.");
      return;
    }
    if (file.size > 12 * 1024 * 1024) {
      setError("That image is larger than 12 MB. Choose a smaller one.");
      return;
    }
    setError("");
    setPatientError("");
    setNotes("");
    setFinalOutcome(null);
    setOutcome("suspicious");
    if (previewUrl) URL.revokeObjectURL(previewUrl);
    setPreviewUrl(URL.createObjectURL(file));
    setFileName(file.name);
    setFileSize(formatSize(file.size));
    setPhase("reading");
  }

  function onDrop(event: React.DragEvent) {
    event.preventDefault();
    dragDepth.current = 0;
    setHot(false);
    takeFile(event.dataTransfer.files?.[0]);
  }

  function clearImage() {
    if (previewUrl) URL.revokeObjectURL(previewUrl);
    setPreviewUrl(null);
    setFileName("");
    setFileSize("");
    setPhase("empty");
    setFinalOutcome(null);
    setNotes("");
    setError("");
    if (inputRef.current) inputRef.current.value = "";
  }

  function confirm(next: Outcome) {
    if (!patientId.trim()) {
      setPatientError("Add the patient ID before confirming.");
      patientRef.current?.focus();
      return;
    }
    setPatientError("");
    setOutcome(next);
    setFinalOutcome(next);
    setPhase("confirmed");
  }

  function focusUpload() {
    uploadRef.current?.scrollIntoView({ behavior: "smooth", block: "start" });
    inputRef.current?.focus();
  }

  const sample = SAMPLES[finalOutcome ?? outcome];
  const imageReady = Boolean(previewUrl);
  const stepState = (index: number) => {
    if (index === 0) return imageReady ? "done" : "active";
    if (index === 1)
      return phase === "reading"
        ? "active"
        : phase === "result" || phase === "confirmed"
          ? "done"
          : "";
    if (index === 2) return phase === "confirmed" ? "done" : phase === "result" ? "active" : "";
    return "";
  };

  return (
    <div className="page">
      <div className="atmosphere" aria-hidden="true" />

      <header className="hero">
        <div className="hero-copy">
          <p className="brand-support">Supports VIA cervical screening</p>
          <div className="brand-row">
            <span className="mark" aria-hidden="true">
              <ViscanMark />
            </span>
            <h1 className="brand-name">VISCAN</h1>
          </div>
          <p className="hero-lede">
            Place the screening image from the visit, review a reading, and confirm it yourself
            before anything is treated as final.
          </p>
          <div className="hero-actions">
            <button type="button" className="choose" onClick={focusUpload}>
              Start with an image
            </button>
            <p className="hero-note">Preview workstation · clinician confirms every result</p>
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
            The image and reading stay on this device if the connection drops. Nothing is sent yet.
          </p>
        </aside>
      </header>

      <section className="session" aria-label="Visit details">
        <label className="field patient-field">
          <span>Patient ID</span>
          <input
            ref={patientRef}
            value={patientId}
            onChange={(event) => {
              setPatientId(event.target.value);
              if (event.target.value.trim()) setPatientError("");
            }}
            placeholder="For example, PT-1042"
            aria-invalid={Boolean(patientError)}
            aria-describedby={patientError ? "patient-error" : "patient-hint"}
          />
          {patientError ? (
            <small id="patient-error">{patientError}</small>
          ) : (
            <small id="patient-hint">Required before you confirm a reading</small>
          )}
        </label>
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
                  <strong>{fileName}</strong>
                  <span>{fileSize}</span>
                </p>
                <div className="frame-actions">
                  <button type="button" onClick={() => inputRef.current?.click()}>
                    Replace
                  </button>
                  <button type="button" onClick={clearImage}>
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
              <p>Drop the capture from this visit, or choose it from this device.</p>
              <button type="button" className="choose" onClick={() => inputRef.current?.click()}>
                Choose image
              </button>
              <p className="formats">JPG, PNG, WEBP · up to 12 MB</p>
            </div>
          )}
          {error ? <p className="error">{error}</p> : null}
        </section>

        <section className="panel result-panel" aria-labelledby="result-title" aria-live="polite">
          <div className="panel-head">
            <div>
              <p className="eyebrow">Reading</p>
              <h2 id="result-title">Interpretation</h2>
            </div>
            <p className="panel-status">
              {phase === "confirmed"
                ? "Confirmed"
                : phase === "reading"
                  ? "Reading in progress"
                  : phase === "result"
                    ? "Awaiting your confirmation"
                    : "Waiting for an image"}
            </p>
          </div>

          {phase === "empty" ? (
            <div className="empty-result">
              <div className="reading-slot">
                <p className="slot-label">Sample reading</p>
                <p className="slot-title">The reading will appear here</p>
                <p className="summary">
                  After you place a screening image, VISCAN prepares a sample reading for this visit.
                  You will see whether it is suspicious or not suspicious, then confirm it yourself.
                </p>
              </div>
              <ul className="outcome-preview" aria-label="Possible readings">
                <li className="outcome-preview-item alert">
                  <span className="outcome-swatch" aria-hidden="true" />
                  <div>
                    <strong>Suspicious</strong>
                    <span>Referral path if you agree</span>
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

          {phase === "reading" ? (
            <div className="reading">
              <div className="reading-slot active">
                <p className="slot-label">Sample reading</p>
                <p className="slot-title">Preparing the reading</p>
                <p className="quiet">
                  The image is in. VISCAN is applying the VIA checklist so you can review the result
                  in a moment.
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

          {phase === "result" || phase === "confirmed" ? (
            <div className={`result ${sample.tone === "clear" ? "is-clear" : "is-alert"}`}>
              {phase === "result" ? (
                <div className="sample-switch" role="group" aria-label="Sample outcome preview">
                  <button
                    type="button"
                    className={outcome === "suspicious" ? "on alert" : "alert"}
                    onClick={() => setOutcome("suspicious")}
                  >
                    Suspicious sample
                  </button>
                  <button
                    type="button"
                    className={outcome === "clear" ? "on clear" : "clear"}
                    onClick={() => setOutcome("clear")}
                  >
                    Not suspicious sample
                  </button>
                </div>
              ) : (
                <p className="seal">
                  <span className="seal-mark" aria-hidden="true" />
                  Confirmed by clinician
                </p>
              )}

              <div className={`verdict ${sample.tone === "clear" ? "clear" : "alert"}`}>
                <p className="verdict-label">
                  {phase === "confirmed" ? "Confirmed result" : "Sample reading · preview"}
                </p>
                <p className="classification">{sample.label}</p>
                <p className="summary">{sample.summary}</p>
              </div>

              <section className="result-block" aria-labelledby="findings-heading">
                <h3 id="findings-heading" className="block-title">
                  Findings
                </h3>
                <dl className="findings">
                  {sample.findings.map((finding) => (
                    <div key={finding.label}>
                      <dt>{finding.label}</dt>
                      <dd>{finding.value}</dd>
                    </div>
                  ))}
                </dl>
              </section>

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

                  <aside className="next-step" aria-labelledby="next-heading">
                    <h3 id="next-heading" className="block-title">
                      If you confirm
                    </h3>
                    <p className="next-lead">{sample.recommendation}</p>
                    <p className="follow">{sample.followUp}</p>
                  </aside>

                  <div className="actions">
                    <button type="button" className="primary" onClick={() => confirm(outcome)}>
                      Confirm this finding
                    </button>
                    <button
                      type="button"
                      className="secondary"
                      onClick={() => confirm(outcome === "suspicious" ? "clear" : "suspicious")}
                    >
                      Record the other finding
                    </button>
                    <button type="button" className="ghost" onClick={clearImage}>
                      Retake
                    </button>
                  </div>
                </>
              ) : (
                <article className="record">
                  <div className="record-head">
                    <h3>Digital record</h3>
                    <p className="record-note">Saved for this visit after clinician confirmation</p>
                  </div>
                  <dl>
                    <div>
                      <dt>Patient ID</dt>
                      <dd>{patientId.trim()}</dd>
                    </div>
                    <div>
                      <dt>Result</dt>
                      <dd className={`record-result ${sample.tone === "clear" ? "clear" : "alert"}`}>
                        {SAMPLES[finalOutcome ?? outcome].label}
                      </dd>
                    </div>
                    <div className="record-image-row">
                      <dt>Image</dt>
                      <dd>
                        <div className="record-image">
                          {previewUrl ? (
                            <img src={previewUrl} alt="" />
                          ) : null}
                          <span>{fileName}</span>
                        </div>
                      </dd>
                    </div>
                    <div>
                      <dt>Clinical notes</dt>
                      <dd>{notes.trim() || "None added"}</dd>
                    </div>
                    <div>
                      <dt>Follow-up</dt>
                      <dd>{SAMPLES[finalOutcome ?? outcome].recommendation}</dd>
                    </div>
                  </dl>
                  <div className="actions">
                    <button type="button" className="secondary" onClick={clearImage}>
                      Start another screening
                    </button>
                  </div>
                </article>
              )}
            </div>
          ) : null}

          <p className="footnote">
            This screen is a preview. The live interpreter is not connected yet, and a result is not
            final until you confirm it.
          </p>
        </section>
      </main>
    </div>
  );
}

"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { type ScreeningPage, type ScreeningQuery, type ScreeningRow, listScreenings } from "@/lib/history";
import { type Verdict, humanize, verdictLabel, verdictTone } from "@/lib/viscan";

const VERDICTS: { value: Verdict | ""; label: string }[] = [
  { value: "", label: "All" },
  { value: "SUSPICIOUS", label: "Suspicious" },
  { value: "NOT_SUSPICIOUS", label: "Not suspicious" },
  { value: "INDETERMINATE", label: "Cannot assess" },
];

const STATUS_LABELS: Record<ScreeningRow["review_status"], string> = {
  pending: "Awaiting review",
  reviewed: "Confirmed",
  disputed: "Disputed",
};

const PER_PAGE = 15;

function formatDate(iso: string | null, withTime = true) {
  if (!iso) return "—";
  const date = new Date(iso.length === 10 ? `${iso}T00:00:00` : iso);
  return date.toLocaleString(undefined, {
    day: "numeric",
    month: "short",
    year: "numeric",
    ...(withTime ? { hour: "2-digit", minute: "2-digit" } : {}),
  });
}

function Stat({ label, value, tone }: { label: string; value: string | number; tone?: string }) {
  return (
    <li className={tone ? `stat ${tone}` : "stat"}>
      <strong>{value}</strong>
      <span>{label}</span>
    </li>
  );
}

function ScreeningItem({ row }: { row: ScreeningRow }) {
  const [open, setOpen] = useState(false);
  const tone = verdictTone(row.screening_verdict);
  const who = row.patient_name || row.patient_external_id || "Unnamed patient";
  const finalTone = row.final_is_suspicious ? "alert" : row.final_via_result === "VIA_NEGATIVE" ? "clear" : "neutral";

  return (
    <li className={`history-item ${tone}`}>
      <div className="history-row">
        <img className="history-thumb" src={row.links.thumbnail} alt="" loading="lazy" />
        <div className="history-main">
          <p className="history-who">
            <strong>{who}</strong>
            {row.patient_name && row.patient_external_id ? <span>{row.patient_external_id}</span> : null}
            <span>Reading #{row.interpretation_id}</span>
          </p>
          <p className="history-meta">
            {formatDate(row.created_at)}
            {row.site ? ` · ${row.site}` : ""}
            {row.age != null ? ` · ${row.age} yrs` : ""}
            {row.hiv_status && row.hiv_status !== "unknown" ? ` · HIV ${row.hiv_status}` : ""}
          </p>
          <div className="history-badges">
            <span className={`verdict-pill ${tone}`}>AI: {verdictLabel(row.screening_verdict)}</span>
            <span className={`status-pill ${row.review_status}`}>{STATUS_LABELS[row.review_status]}</span>
            {row.referral ? <span className="badge">Referred</span> : null}
            {row.notifications ? <span className="badge">Result sent</span> : null}
            {row.coach_sessions ? <span className="badge">Coached</span> : null}
            {row.follow_up_overdue ? <span className="badge overdue">Follow-up overdue</span> : null}
          </div>
        </div>
        <dl className="history-facts">
          <div>
            <dt>Final result</dt>
            <dd className={finalTone}>
              {humanize(row.final_via_result)}
              <small>{row.result_source === "clinician" ? `by ${row.confirmed_by ?? "clinician"}` : "AI, unconfirmed"}</small>
            </dd>
          </div>
          <div>
            <dt>Risk</dt>
            <dd>{row.risk_score ?? "—"}</dd>
          </div>
          <div>
            <dt>Follow-up</dt>
            <dd className={row.follow_up_overdue ? "alert" : undefined}>{formatDate(row.follow_up_due, false)}</dd>
          </div>
        </dl>
        <button
          type="button"
          className="history-toggle"
          aria-expanded={open}
          aria-label={`${open ? "Hide" : "Show"} details for reading ${row.interpretation_id}`}
          onClick={() => setOpen((v) => !v)}
        >
          {open ? "−" : "+"}
        </button>
      </div>

      {open ? (
        <div className="history-detail">
          <figure>
            <img src={row.links.overlay} alt={`AI annotated image for reading ${row.interpretation_id}`} />
          </figure>
          <div className="history-detail-body">
            {row.action ? (
              <p>
                <span className="block-title">Recommended action</span>
                {row.action}
              </p>
            ) : null}
            <ul className="history-detail-facts">
              <li>AI VIA result: {humanize(row.via_result)}</li>
              <li>Confidence: {row.confidence != null ? `${Math.round(row.confidence * 100)}%` : "—"}</li>
              <li>Swede score: {row.swede_score ?? "—"}</li>
              <li>Lesions marked: {row.lesion_count}</li>
              {row.urgency ? <li>Urgency: {humanize(row.urgency)}</li> : null}
              {row.agrees_with_ai !== null ? (
                <li>Clinician {row.agrees_with_ai ? "agreed with" : "disagreed with"} the AI</li>
              ) : null}
              {row.referral ? (
                <li>
                  Referred to {row.referral.hospital ?? "partner hospital"} ({humanize(row.referral.status)})
                </li>
              ) : null}
              {row.notifications ? <li>Result messages sent: {row.notifications}</li> : null}
              {row.symptoms.length ? <li>Symptoms: {row.symptoms.join(", ")}</li> : null}
            </ul>
            {row.clinician_notes ? <blockquote>“{row.clinician_notes}”</blockquote> : null}
            <div className="history-actions">
              <a className="primary link-button" href={row.links.report} target="_blank" rel="noreferrer">
                Report
              </a>
              <Link className="secondary link-button" href={`/care/${row.interpretation_id}`}>
                Care &amp; referral
              </Link>
              <Link className="secondary link-button" href={`/learn?case=${row.interpretation_id}`}>
                Learn with Kezia
              </Link>
            </div>
          </div>
        </div>
      ) : null}
    </li>
  );
}

export function ScreeningsScreen({ initial = {} }: { initial?: ScreeningQuery }) {
  const [search, setSearch] = useState(initial.q ?? "");
  const [query, setQuery] = useState<ScreeningQuery>({ sort: "newest", ...initial, page: 1, per_page: PER_PAGE });
  const [loaded, setLoaded] = useState<{ key: string; data?: ScreeningPage; error?: string } | null>(null);

  const key = JSON.stringify(query);
  const loading = loaded?.key !== key;
  const data = loaded?.data;

  useEffect(() => {
    const timer = setTimeout(() => {
      setQuery((current) => (current.q === (search.trim() || undefined) ? current : { ...current, q: search.trim() || undefined, page: 1 }));
    }, 300);
    return () => clearTimeout(timer);
  }, [search]);

  useEffect(() => {
    let active = true;
    listScreenings(query)
      .then((page) => active && setLoaded({ key, data: page }))
      .catch((err: Error) => active && setLoaded((prev) => ({ key, data: prev?.data, error: err.message })));
    return () => {
      active = false;
    };
  }, [key, query]);

  const update = (patch: Partial<ScreeningQuery>) => setQuery((current) => ({ ...current, ...patch, page: 1 }));
  const summary = data?.summary;
  const filtered =
    Boolean(query.q || query.verdict || query.status || query.from || query.to || query.referred || query.overdue);

  return (
    <div className="page screenings">
      <div className="atmosphere" aria-hidden="true" />
      <header className="page-head">
        <p className="brand-support">Records</p>
        <h1>Past screenings</h1>
        <p className="hero-lede">Every AI reading, what the clinician confirmed, and what happened next.</p>
      </header>

      {summary ? (
        <ul className="stats" aria-label="Screening totals">
          <Stat label="Screenings" value={summary.total} />
          <Stat label="Suspicious" value={summary.suspicious} tone="alert" />
          <Stat label="Awaiting review" value={summary.pending_review} />
          <Stat label="Referred" value={summary.referred} />
          <Stat label="Follow-up overdue" value={summary.follow_up_overdue} tone={summary.follow_up_overdue ? "alert" : undefined} />
          <Stat
            label="Clinician agreed with AI"
            value={summary.agreement_rate != null ? `${Math.round(summary.agreement_rate * 100)}%` : "—"}
            tone="clear"
          />
        </ul>
      ) : null}

      <section className="history-filters" aria-label="Filter screenings">
        <label className="field history-search">
          <span>Search</span>
          <input
            type="search"
            value={search}
            onChange={(event) => setSearch(event.target.value)}
            placeholder="Patient ID, name, site or #reading"
          />
        </label>
        <div className="history-chips" role="group" aria-label="AI verdict">
          {VERDICTS.map((v) => (
            <button
              key={v.label}
              type="button"
              className={(query.verdict ?? "") === v.value ? "filter-chip on" : "filter-chip"}
              aria-pressed={(query.verdict ?? "") === v.value}
              onClick={() => update({ verdict: v.value || undefined })}
            >
              {v.label}
            </button>
          ))}
        </div>
        <div className="history-selects">
          <label className="field">
            <span>Review</span>
            <select value={query.status ?? ""} onChange={(e) => update({ status: (e.target.value || undefined) as ScreeningQuery["status"] })}>
              <option value="">Any</option>
              <option value="pending">Awaiting review</option>
              <option value="reviewed">Confirmed</option>
              <option value="disputed">Disputed</option>
            </select>
          </label>
          <label className="field">
            <span>From</span>
            <input type="date" value={query.from ?? ""} onChange={(e) => update({ from: e.target.value || undefined })} />
          </label>
          <label className="field">
            <span>To</span>
            <input type="date" value={query.to ?? ""} onChange={(e) => update({ to: e.target.value || undefined })} />
          </label>
          <label className="field">
            <span>Sort</span>
            <select value={query.sort} onChange={(e) => update({ sort: e.target.value as ScreeningQuery["sort"] })}>
              <option value="newest">Newest first</option>
              <option value="oldest">Oldest first</option>
              <option value="risk">Highest risk</option>
            </select>
          </label>
          <label className="toggle">
            <input type="checkbox" checked={Boolean(query.referred)} onChange={(e) => update({ referred: e.target.checked })} />
            Referred only
          </label>
          <label className="toggle">
            <input type="checkbox" checked={Boolean(query.overdue)} onChange={(e) => update({ overdue: e.target.checked })} />
            Overdue follow-up
          </label>
          {filtered ? (
            <button
              type="button"
              className="text-button"
              onClick={() => {
                setSearch("");
                setQuery({ sort: query.sort, page: 1, per_page: PER_PAGE });
              }}
            >
              Clear filters
            </button>
          ) : null}
        </div>
      </section>

      {loaded?.error ? (
        <p className="error" role="alert">
          {loaded.error}
        </p>
      ) : null}

      <section aria-labelledby="history-title" aria-busy={loading}>
        <h2 id="history-title" className="block-title">
          {data ? `${data.total} screening${data.total === 1 ? "" : "s"}${filtered ? " match" : ""}` : "Loading screenings…"}
        </h2>
        {data && !data.items.length && !loading ? (
          <div className="history-empty">
            {filtered ? (
              <p>No screenings match these filters.</p>
            ) : (
              <p>
                No screenings yet. <Link href="/screening">Start the first one</Link>.
              </p>
            )}
          </div>
        ) : null}
        <ol className={loading && data ? "history-list stale" : "history-list"}>
          {data?.items.map((row) => <ScreeningItem key={row.interpretation_id} row={row} />)}
        </ol>
        {data && data.pages > 1 ? (
          <nav className="pager" aria-label="Pages">
            <button type="button" disabled={data.page <= 1} onClick={() => setQuery((q) => ({ ...q, page: data.page - 1 }))}>
              ← Previous
            </button>
            <span>
              Page {data.page} of {data.pages}
            </span>
            <button
              type="button"
              disabled={data.page >= data.pages}
              onClick={() => setQuery((q) => ({ ...q, page: data.page + 1 }))}
            >
              Next →
            </button>
          </nav>
        ) : null}
      </section>
    </div>
  );
}

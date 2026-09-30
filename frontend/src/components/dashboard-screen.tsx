"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { CheckedInPatients } from "@/components/intake-panel";
import { type ScreeningPage, type ScreeningQuery, type ScreeningRow, listScreenings } from "@/lib/history";
import { humanize, verdictLabel, verdictTone } from "@/lib/viscan";

const ACTIONS = [
  {
    href: "/screening",
    title: "Start a screening",
    body: "Add the visit details and image, get the AI reading, then confirm it.",
    tone: "primary",
  },
  {
    href: "/",
    title: "Patient check-in",
    body: "Open the welcome screen so patients can check in with Mia before the exam.",
  },
  {
    href: "/screenings",
    title: "Past screenings",
    body: "Search every reading, what was confirmed, referrals and follow-ups.",
  },
  {
    href: "/learn",
    title: "Train with Kezia",
    body: "An AI coach explains results, quizzes you and rehearses counselling.",
  },
];

const PANELS: { id: string; title: string; empty: string; query: ScreeningQuery; more: string }[] = [
  {
    id: "review",
    title: "Needs your review",
    empty: "Every reading has been confirmed.",
    query: { status: "pending", sort: "risk", per_page: 5 },
    more: "/screenings?status=pending&sort=risk",
  },
  {
    id: "overdue",
    title: "Follow-up overdue",
    empty: "No overdue follow-ups.",
    query: { overdue: true, sort: "oldest", per_page: 5 },
    more: "/screenings?overdue=1&sort=oldest",
  },
  {
    id: "recent",
    title: "Recent screenings",
    empty: "No screenings yet.",
    query: { sort: "newest", per_page: 5 },
    more: "/screenings",
  },
];

function when(iso: string | null) {
  if (!iso) return "";
  return new Date(iso).toLocaleString(undefined, { day: "numeric", month: "short", hour: "2-digit", minute: "2-digit" });
}

function MiniRow({ row, panel }: { row: ScreeningRow; panel: string }) {
  const tone = verdictTone(row.screening_verdict);
  return (
    <li>
      <Link href={`/screenings?q=%23${row.interpretation_id}`} className="mini-row">
        <span className={`case-dot ${tone}`} aria-hidden="true" />
        <span className="mini-main">
          <strong>{row.patient_name || row.patient_external_id || `Reading #${row.interpretation_id}`}</strong>
          <small>
            {verdictLabel(row.screening_verdict)} · {humanize(row.final_via_result)}
            {row.risk_score != null ? ` · risk ${row.risk_score}` : ""}
          </small>
        </span>
        <small className="mini-when">
          {panel === "overdue" && row.follow_up_due ? `Due ${row.follow_up_due}` : when(row.created_at)}
        </small>
      </Link>
    </li>
  );
}

function ScreeningPanel({ panel }: { panel: (typeof PANELS)[number] }) {
  const [data, setData] = useState<ScreeningPage | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    let active = true;
    listScreenings(panel.query)
      .then((page) => active && setData(page))
      .catch((err: Error) => active && setError(err.message));
    return () => {
      active = false;
    };
  }, [panel.query]);

  return (
    <section className="dash-panel" aria-labelledby={`dash-${panel.id}`}>
      <div className="dash-panel-head">
        <h2 id={`dash-${panel.id}`} className="block-title">
          {panel.title}
          {data ? <span className="count">{data.total}</span> : null}
        </h2>
        <Link href={panel.more} className="back-link">
          See all →
        </Link>
      </div>
      {error ? <p className="error">{error}</p> : null}
      {data && !data.items.length ? <p className="quiet small">{panel.empty}</p> : null}
      {!data && !error ? <p className="quiet small">Loading…</p> : null}
      {data?.items.length ? (
        <ul className="mini-list">
          {data.items.map((row) => (
            <MiniRow key={row.interpretation_id} row={row} panel={panel.id} />
          ))}
        </ul>
      ) : null}
    </section>
  );
}

export function DashboardScreen() {
  const router = useRouter();
  const [summary, setSummary] = useState<ScreeningPage["summary"] | null>(null);

  useEffect(() => {
    let active = true;
    listScreenings({ per_page: 1 })
      .then((page) => active && setSummary(page.summary))
      .catch(() => undefined);
    return () => {
      active = false;
    };
  }, []);

  return (
    <div className="page dashboard">
      <div className="atmosphere" aria-hidden="true" />
      <header className="page-head">
        <p className="brand-support">Supports VIA cervical screening</p>
        <h1>Overview</h1>
        <p className="hero-lede">
          Check patients in, screen, confirm every AI reading yourself, and follow each patient through to care.
        </p>
      </header>

      <ul className="dash-actions">
        {ACTIONS.map((a) => (
          <li key={a.href}>
            <Link href={a.href} className={a.tone === "primary" ? "dash-action primary-action" : "dash-action"}>
              <strong>{a.title}</strong>
              <span>{a.body}</span>
            </Link>
          </li>
        ))}
      </ul>

      {summary ? (
        <ul className="stats" aria-label="Screening totals">
          <li className="stat">
            <strong>{summary.total}</strong>
            <span>Screenings</span>
          </li>
          <li className="stat alert">
            <strong>{summary.suspicious}</strong>
            <span>Suspicious</span>
          </li>
          <li className="stat">
            <strong>{summary.pending_review}</strong>
            <span>Awaiting review</span>
          </li>
          <li className="stat">
            <strong>{summary.referred}</strong>
            <span>Referred</span>
          </li>
          <li className={summary.follow_up_overdue ? "stat alert" : "stat"}>
            <strong>{summary.follow_up_overdue}</strong>
            <span>Follow-up overdue</span>
          </li>
          <li className="stat clear">
            <strong>{summary.agreement_rate != null ? `${Math.round(summary.agreement_rate * 100)}%` : "—"}</strong>
            <span>Clinician agreed with AI</span>
          </li>
        </ul>
      ) : null}

      <div className="dash-grid">
        <CheckedInPatients onSelect={(intake) => router.push(`/screening?intake=${intake.id}`)} />
        {PANELS.map((panel) => (
          <ScreeningPanel key={panel.id} panel={panel} />
        ))}
      </div>
    </div>
  );
}

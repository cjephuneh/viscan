"use client";

import { useEffect, useState } from "react";
import { type ScreeningSummary, listScreenings } from "@/lib/history";
import {
  type ClinicMetrics,
  fetchClinicMetrics,
  formatLatency,
  formatPercent,
  formatRate,
  isoDaysAgo,
} from "@/lib/metrics";

type Throughput = { week: number | null; month: number | null };

const VERDICT_COLORS = {
  suspicious: "#c0392b",
  clear: "#2f6b52",
  indeterminate: "#c45b93",
  other: "#8aa396",
};

const REVIEW_COLORS = {
  reviewed: "#2f6b52",
  pending: "#c45b93",
  disputed: "#c0392b",
};

function Meter({ value, color }: { value: number | null; color?: string }) {
  if (value == null) return null;
  return (
    <div className="perf-meter" aria-hidden="true">
      <i style={{ width: `${value}%`, ...(color ? { background: color } : {}) }} />
    </div>
  );
}

function PerfCard({
  label,
  value,
  hint,
  meter,
  tone,
}: {
  label: string;
  value: string | number;
  hint: string;
  meter?: number | null;
  tone?: "alert" | "clear" | "warn";
}) {
  return (
    <article className={tone ? `perf-card ${tone}` : "perf-card"}>
      <p className="perf-label">{label}</p>
      <p className="perf-value">{value}</p>
      <p className="perf-hint">{hint}</p>
      <Meter value={meter ?? null} />
    </article>
  );
}

function ratio(part: number, whole: number): number | null {
  if (!whole) return null;
  return part / whole;
}

function BarChart({
  title,
  bars,
  emptyNote,
}: {
  title: string;
  bars: { label: string; value: number; color: string }[];
  emptyNote: string;
}) {
  const max = Math.max(...bars.map((b) => b.value), 1);
  const hasData = bars.some((b) => b.value > 0);

  return (
    <div className="perf-chart" aria-label={title}>
      <h3 className="perf-subhead">{title}</h3>
      {!hasData ? <p className="perf-empty">{emptyNote}</p> : null}
      <div className="perf-bars" role="img" aria-label={`${title} bar chart`}>
        {bars.map((bar) => {
          const height = Math.max(6, Math.round((bar.value / max) * 120));
          return (
            <div key={bar.label} className="perf-bar">
              <strong className="perf-bar-value">{bar.value}</strong>
              <span className="perf-bar-fill" style={{ height: `${height}px`, background: bar.color }} />
              <span className="perf-bar-label">{bar.label}</span>
            </div>
          );
        })}
      </div>
    </div>
  );
}

function DonutChart({
  title,
  slices,
  center,
  emptyNote,
}: {
  title: string;
  slices: { label: string; value: number; color: string }[];
  center: string;
  emptyNote: string;
}) {
  const total = slices.reduce((sum, s) => sum + s.value, 0);
  const radius = 42;
  const circumference = 2 * Math.PI * radius;
  let offset = 0;

  return (
    <div className="perf-chart" aria-label={title}>
      <h3 className="perf-subhead">{title}</h3>
      {!total ? <p className="perf-empty">{emptyNote}</p> : null}
      <div className="perf-donut-wrap">
        <svg className="perf-donut" viewBox="0 0 120 120" role="img" aria-label={`${title} donut chart`}>
          <circle className="perf-donut-track" cx="60" cy="60" r={radius} />
          {total
            ? slices
                .filter((s) => s.value > 0)
                .map((slice) => {
                  const length = (slice.value / total) * circumference;
                  const node = (
                    <circle
                      key={slice.label}
                      className="perf-donut-slice"
                      cx="60"
                      cy="60"
                      r={radius}
                      stroke={slice.color}
                      strokeDasharray={`${length} ${circumference - length}`}
                      strokeDashoffset={-offset}
                    />
                  );
                  offset += length;
                  return node;
                })
            : null}
          <text x="60" y="56" textAnchor="middle" className="perf-donut-center">
            {center}
          </text>
          <text x="60" y="72" textAnchor="middle" className="perf-donut-caption">
            total
          </text>
        </svg>
        <ul className="perf-legend">
          {slices.map((slice) => (
            <li key={slice.label}>
              <i style={{ background: slice.color }} aria-hidden="true" />
              <span>{slice.label}</span>
              <strong>{slice.value}</strong>
            </li>
          ))}
        </ul>
      </div>
    </div>
  );
}

function HBarChart({
  title,
  rows,
  emptyNote,
}: {
  title: string;
  rows: { label: string; value: number; color: string }[];
  emptyNote: string;
}) {
  const max = Math.max(...rows.map((r) => r.value), 1);
  const hasData = rows.some((r) => r.value > 0);

  return (
    <div className="perf-chart" aria-label={title}>
      <h3 className="perf-subhead">{title}</h3>
      {!hasData ? <p className="perf-empty">{emptyNote}</p> : null}
      <ul className="perf-hbars">
        {rows.map((row) => (
          <li key={row.label}>
            <div className="perf-hbar-meta">
              <span>{row.label}</span>
              <strong>{row.value}</strong>
            </div>
            <div className="perf-hbar-track" aria-hidden="true">
              <i style={{ width: `${Math.max(row.value ? 4 : 0, (row.value / max) * 100)}%`, background: row.color }} />
            </div>
          </li>
        ))}
      </ul>
    </div>
  );
}

export function PerformanceMetrics({ summary = null }: { summary?: ScreeningSummary | null }) {
  const [metrics, setMetrics] = useState<ClinicMetrics | null>(null);
  const [throughput, setThroughput] = useState<Throughput>({ week: null, month: null });
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let active = true;
    setLoading(true);

    const load = async () => {
      const results = await Promise.allSettled([
        fetchClinicMetrics(),
        listScreenings({ from: isoDaysAgo(6), per_page: 1 }),
        listScreenings({ from: isoDaysAgo(29), per_page: 1 }),
      ]);
      if (!active) return;

      const clinic = results[0].status === "fulfilled" ? results[0].value : null;
      const week = results[1].status === "fulfilled" ? results[1].value.summary.total : null;
      const month = results[2].status === "fulfilled" ? results[2].value.summary.total : null;
      const failures = results.filter((r) => r.status === "rejected") as PromiseRejectedResult[];

      setMetrics(clinic);
      setThroughput({ week, month });
      setError(
        !clinic && failures[0]
          ? failures[0].reason instanceof Error
            ? failures[0].reason.message
            : "Could not load performance metrics."
          : "",
      );
      setLoading(false);
    };

    load().catch((err: Error) => {
      if (!active) return;
      setError(err.message);
      setLoading(false);
    });

    return () => {
      active = false;
    };
  }, []);

  const total = summary?.total ?? metrics?.total_interpretations ?? 0;
  const reviewed = summary?.reviewed ?? metrics?.by_review_status?.reviewed ?? 0;
  const pending = summary?.pending_review ?? metrics?.by_review_status?.pending ?? 0;
  const disputed = summary?.disputed ?? metrics?.by_review_status?.disputed ?? 0;
  const suspicious = summary?.suspicious ?? metrics?.by_verdict?.SUSPICIOUS ?? 0;
  const clear = summary?.not_suspicious ?? metrics?.by_verdict?.NOT_SUSPICIOUS ?? 0;
  const indeterminate = summary?.indeterminate ?? metrics?.by_verdict?.INDETERMINATE ?? 0;
  const agreement = metrics?.clinician_agreement?.agreement_rate ?? summary?.agreement_rate ?? null;
  const kappa = metrics?.clinician_agreement?.cohens_kappa ?? null;
  const histology = metrics?.vs_histology_cin2_plus;
  const hasHistology = Boolean(histology && histology.cases_with_reference > 0);
  const reviewDone = ratio(reviewed, total);
  const pendingLoad = ratio(pending, total);
  const clearShare = ratio(clear, total);
  const engineEntries = Object.entries(metrics?.by_engine ?? {}).sort((a, b) => b[1] - a[1]);

  const lastAt = summary?.last_screening_at
    ? new Date(summary.last_screening_at).toLocaleString(undefined, {
        day: "numeric",
        month: "short",
        year: "numeric",
        hour: "2-digit",
        minute: "2-digit",
      })
    : "—";

  const qualityBars = hasHistology && histology
    ? [
        { label: "Sensitivity", value: Math.round((histology.sensitivity ?? 0) * 100), color: "#2f6b52" },
        { label: "Specificity", value: Math.round((histology.specificity ?? 0) * 100), color: "#245c42" },
        { label: "PPV", value: Math.round((histology.ppv ?? 0) * 100), color: "#c45b93" },
        { label: "NPV", value: Math.round((histology.npv ?? 0) * 100), color: "#8a3d78" },
      ]
    : [
        { label: "Sensitivity", value: 0, color: "#2f6b52" },
        { label: "Specificity", value: 0, color: "#245c42" },
        { label: "PPV", value: 0, color: "#c45b93" },
        { label: "NPV", value: 0, color: "#8a3d78" },
      ];

  return (
    <section className="perf-panel" aria-label="System performance">
      <div className="perf-head">
        <div>
          <h2 className="dash-section-title">System performance</h2>
          <p className="dash-section-note">
            Live clinic use, review quality, and reading speed from real records in this system.
          </p>
        </div>
        <p className="perf-updated">
          {total ? (
            <>
              Last reading <strong>{lastAt}</strong>
            </>
          ) : (
            <>No screenings stored yet — charts stay at zero until readings exist.</>
          )}
        </p>
      </div>

      {error ? (
        <p className="error" role="alert">
          {error}
        </p>
      ) : null}

      {loading ? <p className="quiet small">Loading performance…</p> : null}

      {!loading && (metrics || summary) ? (
        <>
          <div className="perf-charts">
            <DonutChart
              title="Review status"
              center={String(total)}
              emptyNote="No readings to split yet."
              slices={[
                { label: "Confirmed", value: reviewed, color: REVIEW_COLORS.reviewed },
                { label: "Awaiting", value: pending, color: REVIEW_COLORS.pending },
                { label: "Disputed", value: disputed, color: REVIEW_COLORS.disputed },
              ]}
            />
            <BarChart
              title="AI verdict mix"
              emptyNote="Verdict bars fill as screenings are saved."
              bars={[
                { label: "Suspicious", value: suspicious, color: VERDICT_COLORS.suspicious },
                { label: "Clear", value: clear, color: VERDICT_COLORS.clear },
                { label: "Cannot assess", value: indeterminate, color: VERDICT_COLORS.indeterminate },
              ]}
            />
            <BarChart
              title="Throughput"
              emptyNote="Weekly and monthly counts appear after screenings."
              bars={[
                { label: "7 days", value: throughput.week ?? 0, color: "#c45b93" },
                { label: "30 days", value: throughput.month ?? 0, color: "#8a3d78" },
                { label: "All time", value: total, color: "#2f6b52" },
              ]}
            />
            <HBarChart
              title="Quality vs reference"
              emptyNote={
                hasHistology
                  ? "Reference-linked quality scores."
                  : "Add histology/colposcopy diagnoses to unlock sensitivity charts."
              }
              rows={qualityBars.map((row) => ({
                ...row,
                value: hasHistology ? row.value : 0,
              }))}
            />
          </div>

          <div className="perf-grid">
            <PerfCard
              label="Clinician agreement"
              value={formatPercent(agreement)}
              hint={
                metrics?.clinician_agreement?.reviewed
                  ? `${metrics.clinician_agreement.reviewed} confirmed reading${metrics.clinician_agreement.reviewed === 1 ? "" : "s"}`
                  : "Share of confirmed readings matching AI"
              }
              meter={formatRate(agreement)}
              tone="clear"
            />
            <PerfCard
              label="Chance-corrected agreement"
              value={kappa == null ? "—" : kappa.toFixed(2)}
              hint="Cohen’s κ from AI vs clinician pairs"
              meter={kappa == null ? null : formatRate((kappa + 1) / 2)}
            />
            <PerfCard
              label="Review completion"
              value={formatPercent(reviewDone)}
              hint={`${reviewed} confirmed · ${pending} waiting · ${disputed} disputed`}
              meter={formatRate(reviewDone)}
            />
            <PerfCard
              label="Awaiting review"
              value={pending}
              hint={pendingLoad == null ? "Readings still needing confirmation" : `${formatPercent(pendingLoad)} of all screenings`}
              meter={formatRate(pendingLoad)}
              tone={pending > 0 ? "warn" : undefined}
            />
            <PerfCard
              label="Average risk score"
              value={metrics?.average_risk_score ?? "—"}
              hint="Mean risk across stored readings"
            />
            <PerfCard
              label="Average reading time"
              value={formatLatency(metrics?.average_latency_ms)}
              hint="Mean interpreter latency for completed readings"
            />
            <PerfCard label="Last 7 days" value={throughput.week ?? "—"} hint="Screenings recorded in the past week" />
            <PerfCard label="Last 30 days" value={throughput.month ?? "—"} hint="Screenings recorded in the past month" />
            <PerfCard
              label="Clear readings"
              value={clear}
              hint={clearShare == null ? "Not suspicious AI verdicts" : `${formatPercent(clearShare)} of all screenings`}
              meter={formatRate(clearShare)}
              tone="clear"
            />
            <PerfCard
              label="Cannot assess"
              value={indeterminate}
              hint="Indeterminate AI verdicts needing a closer look"
              tone={indeterminate > 0 ? "warn" : undefined}
            />
            <PerfCard label="Referrals" value={summary?.referred ?? 0} hint="Screenings marked referred for follow-up care" />
            <PerfCard
              label="Follow-up overdue"
              value={summary?.follow_up_overdue ?? 0}
              hint="Cases past their follow-up due date"
              tone={(summary?.follow_up_overdue ?? 0) > 0 ? "alert" : undefined}
            />
          </div>

          {engineEntries.length ? (
            <div className="perf-engines" aria-label="Reading engines">
              <h3 className="perf-subhead">Reading engines in use</h3>
              <ul className="perf-engine-list">
                {engineEntries.map(([engine, count]) => {
                  const share = formatRate(ratio(count, metrics?.total_interpretations ?? 0));
                  return (
                    <li key={engine}>
                      <div className="perf-engine-row">
                        <span>{engine}</span>
                        <strong>{count}</strong>
                      </div>
                      <Meter value={share} color="#c45b93" />
                    </li>
                  );
                })}
              </ul>
            </div>
          ) : null}
        </>
      ) : null}
    </section>
  );
}

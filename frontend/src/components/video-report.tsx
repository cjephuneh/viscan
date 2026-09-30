"use client";

import { useEffect, useState } from "react";
import { type VideoReport as VideoReportStatus, getVideoReport, videoPlayerUrl } from "@/lib/viscan";

const POLL_MS = 5000;
// Anam rendering takes a few minutes at most; stop polling after this.
const GIVE_UP_MS = 15 * 60 * 1000;

type State =
  | { kind: "preparing"; status: VideoReportStatus["status"] | "creating" }
  | { kind: "ready"; report: VideoReportStatus }
  | { kind: "failed"; message: string }
  | { kind: "unavailable" };

/**
 * Avatar video report for a confirmed reading.
 *
 * The interpreter asks ai-avatar to render the video as soon as the clinician
 * confirms the result; we poll the status endpoint and embed the player once
 * the video is ready.
 */
export function VideoReport({
  interpretationId,
  enabled = true,
  pollMs = POLL_MS,
}: {
  interpretationId: number;
  /** Set to false while the reading is not yet clinician-confirmed. */
  enabled?: boolean;
  pollMs?: number;
}) {
  const [state, setState] = useState<State>({ kind: "preparing", status: "creating" });

  useEffect(() => {
    if (!enabled) return;
    let active = true;
    let timer: ReturnType<typeof setTimeout> | undefined;
    const startedAt = Date.now();
    let failures = 0;

    const schedule = () => {
      if (!active) return;
      if (Date.now() - startedAt > GIVE_UP_MS) {
        setState({ kind: "failed", message: "The video is taking longer than expected. Open it later from the screening list." });
        return;
      }
      timer = setTimeout(poll, pollMs);
    };

    const poll = async () => {
      try {
        const report = await getVideoReport(interpretationId);
        if (!active) return;
        failures = 0;
        if (!report) {
          setState({ kind: "preparing", status: "creating" });
          return schedule();
        }
        if (report.status === "completed" && report.video_url) {
          setState({ kind: "ready", report });
          return;
        }
        if (report.status === "failed") {
          setState({ kind: "failed", message: "The video could not be generated for this reading." });
          return;
        }
        setState({ kind: "preparing", status: report.status });
        schedule();
      } catch {
        if (!active) return;
        failures += 1;
        // The service may be down (or not deployed): after a few misses, stop nagging.
        if (failures >= 3) setState({ kind: "unavailable" });
        else schedule();
      }
    };

    void poll();
    return () => {
      active = false;
      if (timer) clearTimeout(timer);
    };
  }, [interpretationId, enabled, pollMs]);

  if (!enabled) return null;

  const playerUrl = videoPlayerUrl(interpretationId);

  return (
    <article className="record video-report" data-coach="video-report" aria-live="polite">
      <div className="record-head">
        <h3>Video report</h3>
        <p className="record-note">
          {state.kind === "ready"
            ? "Explains the confirmed result and next steps. Play it with the patient or share the link."
            : "Generated from the confirmed result by the VIScan avatar."}
        </p>
      </div>

      {state.kind === "ready" ? (
        <>
          <div className="video-frame">
            <iframe
              src={playerUrl}
              title="Video report"
              allow="autoplay; fullscreen"
              allowFullScreen
              loading="lazy"
            />
          </div>
          <div className="actions">
            <a className="secondary link-button" href={playerUrl} target="_blank" rel="noreferrer">
              Open player
            </a>
            {state.report.video_url ? (
              <a className="ghost link-button" href={state.report.video_url} target="_blank" rel="noreferrer">
                Download video
              </a>
            ) : null}
          </div>
        </>
      ) : state.kind === "preparing" ? (
        <p className="video-status" role="status">
          <span className="spinner" aria-hidden="true" />
          {state.status === "creating"
            ? "Preparing the video report…"
            : state.status === "running"
              ? "Rendering the video (usually one to two minutes)…"
              : "Video queued for rendering…"}
        </p>
      ) : state.kind === "failed" ? (
        <p className="video-status error" role="status">
          {state.message}
        </p>
      ) : (
        <p className="video-status muted" role="status">
          Video reports are not available right now. The written result above is unaffected.
        </p>
      )}
    </article>
  );
}

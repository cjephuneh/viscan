"use client";

import { useEffect, useRef, useState } from "react";
import { useAnamAvatar } from "@/lib/use-anam";
import {
  type VideoReport as VideoReportStatus,
  getVideoReport,
  getVideoSession,
  videoPlayerUrl,
} from "@/lib/viscan";

const POLL_MS = 5000;
// Anam rendering takes a few minutes at most; stop polling after this.
const GIVE_UP_MS = 15 * 60 * 1000;
// Close the live session this long after the avatar finished the script.
const LIVE_IDLE_CLOSE_MS = 8000;
const VIDEO_ID = "report-live-video";

type Mp4State =
  | { kind: "preparing"; status: VideoReportStatus["status"] | "creating" }
  | { kind: "ready"; report: VideoReportStatus }
  | { kind: "failed"; message: string }
  | { kind: "unavailable" };

/**
 * Avatar video report for a confirmed reading.
 *
 * Two paths to the same script:
 *  - **Live**: as soon as the report exists (about a second after confirmation)
 *    the clinician can press "Present now"; the avatar streams over WebRTC and
 *    speaks the confirmed report within a few seconds.
 *  - **Recording**: the MP4 renders in the background (1–2 min). We poll its
 *    status and embed the player once it is ready; it is what the care page and
 *    shared links use later.
 */
export function VideoReport({
  interpretationId,
  enabled = true,
  pollMs = POLL_MS,
  idleCloseMs = LIVE_IDLE_CLOSE_MS,
}: {
  interpretationId: number;
  /** Set to false while the reading is not yet clinician-confirmed. */
  enabled?: boolean;
  pollMs?: number;
  idleCloseMs?: number;
}) {
  const [mp4, setMp4] = useState<Mp4State>({ kind: "preparing", status: "creating" });
  const [reportExists, setReportExists] = useState(false);
  const [starting, setStarting] = useState(false);
  const [liveError, setLiveError] = useState("");
  const [presented, setPresented] = useState(false);
  const [spokenAll, setSpokenAll] = useState(false);
  const scriptRef = useRef<string>("");
  const spokenRef = useRef(false);
  const avatar = useAnamAvatar(VIDEO_ID, "the avatar");
  const { talk, stop, status: liveStatus, speaking } = avatar;

  // --- MP4 status polling -------------------------------------------------
  useEffect(() => {
    if (!enabled) return;
    let active = true;
    let timer: ReturnType<typeof setTimeout> | undefined;
    const startedAt = Date.now();
    let failures = 0;

    const schedule = () => {
      if (!active) return;
      if (Date.now() - startedAt > GIVE_UP_MS) {
        setMp4({ kind: "failed", message: "The recording is taking longer than expected. It will be on the care page later." });
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
          setMp4({ kind: "preparing", status: "creating" });
          return schedule();
        }
        setReportExists(true);
        if (report.status === "completed" && report.video_url) {
          setMp4({ kind: "ready", report });
          return;
        }
        if (report.status === "failed") {
          setMp4({ kind: "failed", message: "The recording could not be generated for this reading." });
          return;
        }
        setMp4({ kind: "preparing", status: report.status });
        schedule();
      } catch {
        if (!active) return;
        failures += 1;
        // The service may be down (or not deployed): after a few misses, stop nagging.
        if (failures >= 3) setMp4({ kind: "unavailable" });
        else schedule();
      }
    };

    void poll();
    return () => {
      active = false;
      if (timer) clearTimeout(timer);
    };
  }, [interpretationId, enabled, pollMs]);

  // --- Live presentation ---------------------------------------------------
  async function present() {
    setStarting(true);
    setLiveError("");
    spokenRef.current = false;
    setSpokenAll(false);
    try {
      const session = await getVideoSession(interpretationId);
      if (!session) {
        setLiveError("The report is still being prepared. Try again in a moment.");
        return;
      }
      scriptRef.current = session.generated_script;
      setReportExists(true);
      // Presentation only: no microphone, so room noise cannot interrupt the avatar.
      await avatar.start(session.session_token, {}, { disableInputAudio: true });
    } catch (err) {
      setLiveError((err as Error).message || "Could not start the live presentation.");
    } finally {
      setStarting(false);
    }
  }

  // Speak the confirmed script (verbatim) once the stream is on screen.
  useEffect(() => {
    if (liveStatus !== "live" || spokenRef.current || !scriptRef.current) return;
    spokenRef.current = true;
    const paragraphs = scriptRef.current.split(/\n\s*\n/).map((p) => p.trim()).filter(Boolean);
    void (async () => {
      for (const paragraph of paragraphs) {
        const sent = await talk(paragraph);
        if (!sent) return;
      }
      setSpokenAll(true);
    })();
  }, [liveStatus, talk]);

  // Close the session a few seconds after the avatar has finished speaking.
  useEffect(() => {
    if (liveStatus !== "live" || !spokenAll || speaking) return;
    const timer = setTimeout(() => {
      setPresented(true);
      void stop();
    }, idleCloseMs);
    return () => clearTimeout(timer);
  }, [liveStatus, speaking, spokenAll, stop, idleCloseMs]);

  if (!enabled) return null;

  const live = avatar.status === "connecting" || avatar.status === "live";
  // Errors raised while starting are in liveError; a dropped connection surfaces through the hook.
  const shownError = liveError || (avatar.status === "error" ? avatar.error : "");
  const playerUrl = videoPlayerUrl(interpretationId);
  const canPresent = reportExists && !live && !starting;

  return (
    <article className="record video-report" data-coach="video-report" aria-live="polite">
      <div className="record-head">
        <h3>Video report</h3>
        <p className="record-note">
          The avatar explains the confirmed result and next steps. Present it live now, or use the recording later.
        </p>
      </div>

      {live ? (
        <>
          <div className={`video-frame live ${avatar.speaking ? "speaking" : ""}`}>
            <video id={VIDEO_ID} autoPlay playsInline className={avatar.status === "live" ? "on" : ""} />
            <span className="live-badge">
              <span className="live-dot" aria-hidden="true" />
              {avatar.status === "live" ? "Live · AI avatar" : "Connecting…"}
            </span>
            {avatar.caption && avatar.status === "live" ? <p className="live-caption">{avatar.caption}</p> : null}
          </div>
          <div className="actions">
            <button
              type="button"
              className="ghost"
              onClick={() => {
                setPresented(true);
                void avatar.stop();
              }}
            >
              Stop
            </button>
          </div>
        </>
      ) : mp4.kind === "ready" ? (
        <div className="video-frame">
          <iframe src={playerUrl} title="Video report" allow="autoplay; fullscreen" allowFullScreen loading="lazy" />
        </div>
      ) : null}

      {!live ? (
        <div className="actions">
          <button type="button" className="primary" onClick={present} disabled={!canPresent}>
            {starting
              ? "Connecting…"
              : presented
                ? "Present again"
                : reportExists
                  ? "Present now with the patient"
                  : "Preparing the report…"}
          </button>
          {mp4.kind === "ready" ? (
            <>
              <a className="secondary link-button" href={playerUrl} target="_blank" rel="noreferrer">
                Open player
              </a>
              {mp4.report.video_url ? (
                <a className="ghost link-button" href={mp4.report.video_url} target="_blank" rel="noreferrer">
                  Download video
                </a>
              ) : null}
            </>
          ) : null}
        </div>
      ) : null}

      {shownError ? <p className="error">{shownError}</p> : null}

      {mp4.kind === "preparing" ? (
        <p className="video-status" role="status">
          <span className="spinner" aria-hidden="true" />
          {mp4.status === "creating"
            ? "Preparing the video report…"
            : mp4.status === "running"
              ? "Recording for the record (usually one to two minutes)…"
              : "Recording queued…"}
        </p>
      ) : mp4.kind === "failed" ? (
        <p className="video-status error" role="status">
          {mp4.message}
        </p>
      ) : mp4.kind === "unavailable" ? (
        <p className="video-status muted" role="status">
          Video reports are not available right now. The written result above is unaffected.
        </p>
      ) : null}
    </article>
  );
}

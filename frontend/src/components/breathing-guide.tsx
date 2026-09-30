"use client";

import { useEffect, useState } from "react";

const PHASES = [
  { id: "in", label: "Breathe in", seconds: 4 },
  { id: "hold", label: "Hold", seconds: 4 },
  { id: "out", label: "Breathe out", seconds: 6 },
] as const;
const CYCLE = PHASES.reduce((sum, phase) => sum + phase.seconds, 0);

export function BreathingGuide({ rounds, onClose }: { rounds: number; onClose: () => void }) {
  const [elapsed, setElapsed] = useState(0);
  const total = rounds * CYCLE;
  const finished = elapsed >= total;

  useEffect(() => {
    if (finished) return;
    const timer = window.setInterval(() => setElapsed((s) => s + 1), 1000);
    return () => window.clearInterval(timer);
  }, [finished]);

  const inCycle = elapsed % CYCLE;
  let offset = 0;
  let phase: (typeof PHASES)[number] = PHASES[0];
  for (const candidate of PHASES) {
    if (inCycle < offset + candidate.seconds) {
      phase = candidate;
      break;
    }
    offset += candidate.seconds;
  }
  const count = phase.seconds - (inCycle - offset);
  const round = Math.min(rounds, Math.floor(elapsed / CYCLE) + 1);

  return (
    <div className="breathing" role="dialog" aria-label="Breathing exercise">
      <div
        className={`breath-orb ${finished ? "rest" : phase.id}`}
        style={{ transitionDuration: `${phase.seconds}s` }}
        aria-hidden="true"
      >
        <span className="breath-ring" />
        <span className="breath-core" />
      </div>
      <p className="breath-label" aria-live="polite">
        {finished ? "Well done" : phase.label}
      </p>
      <p className="breath-count">{finished ? "Notice how your body feels now." : count}</p>
      <p className="breath-round">
        {finished ? `${rounds} ${rounds === 1 ? "round" : "rounds"} complete` : `Round ${round} of ${rounds}`}
      </p>
      <button type="button" className="ghost" onClick={onClose}>
        {finished ? "Close" : "Stop"}
      </button>
    </div>
  );
}

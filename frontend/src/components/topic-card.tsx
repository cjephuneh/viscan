import { TOPICS } from "@/lib/intake";

function Illustration({ topic }: { topic: string }) {
  const common = { fill: "none", stroke: "currentColor", strokeWidth: 2.2, strokeLinecap: "round" as const };
  switch (topic) {
    case "what_is_via":
    case "the_vinegar_test":
      return (
        <svg viewBox="0 0 96 96" aria-hidden="true">
          <circle cx="48" cy="50" r="30" {...common} />
          <ellipse cx="48" cy="50" rx="7" ry="4" fill="currentColor" opacity="0.35" />
          <path d="M60 38c5 3 7 8 6 13" {...common} strokeDasharray="3 5" />
          <path d="M70 12v14M64 18l6-6 6 6" {...common} />
        </svg>
      );
    case "why_screening_matters":
      return (
        <svg viewBox="0 0 96 96" aria-hidden="true">
          <path d="M48 16l26 10v20c0 18-12 28-26 34-14-6-26-16-26-34V26z" {...common} />
          <path d="M36 48l9 9 16-18" {...common} />
        </svg>
      );
    case "what_to_expect":
    case "the_speculum":
      return (
        <svg viewBox="0 0 96 96" aria-hidden="true">
          <path d="M14 66h68M22 66V52h52v14" {...common} />
          <circle cx="30" cy="42" r="7" {...common} />
          <path d="M40 50c8-8 20-10 30-6" {...common} />
          <path d="M76 20l-6 12M84 30l-10 6" {...common} opacity="0.6" />
        </svg>
      );
    case "how_long":
      return (
        <svg viewBox="0 0 96 96" aria-hidden="true">
          <circle cx="48" cy="50" r="30" {...common} />
          <path d="M48 32v18l12 8" {...common} />
          <path d="M40 12h16" {...common} />
        </svg>
      );
    case "results_same_day":
      return (
        <svg viewBox="0 0 96 96" aria-hidden="true">
          <rect x="30" y="14" width="36" height="68" rx="7" {...common} />
          <path d="M38 36h20M38 46h14" {...common} />
          <path d="M40 62l6 6 11-12" {...common} />
        </svg>
      );
    case "if_positive_treatment":
      return (
        <svg viewBox="0 0 96 96" aria-hidden="true">
          <path d="M48 80S18 62 18 40a15 15 0 0130-6 15 15 0 0130 6c0 22-30 40-30 40z" {...common} />
          <path d="M48 38v20M38 48h20" {...common} />
        </svg>
      );
    case "privacy":
      return (
        <svg viewBox="0 0 96 96" aria-hidden="true">
          <rect x="26" y="42" width="44" height="36" rx="6" {...common} />
          <path d="M34 42V32a14 14 0 0128 0v10" {...common} />
          <circle cx="48" cy="60" r="4" fill="currentColor" />
        </svg>
      );
    default:
      return (
        <svg viewBox="0 0 96 96" aria-hidden="true">
          <path d="M20 56c8-4 14-4 20 0s12 4 20 0 14-4 20 0" {...common} />
          <path d="M20 40c8-4 14-4 20 0s12 4 20 0 14-4 20 0" {...common} opacity="0.55" />
          <circle cx="48" cy="72" r="4" fill="currentColor" />
        </svg>
      );
  }
}

export function TopicCard({ topic }: { topic: string }) {
  const content = TOPICS[topic];
  if (!content) return null;
  return (
    <article className="topic-card" key={topic}>
      <div className="topic-art">
        <Illustration topic={topic} />
      </div>
      <div>
        <p className="eyebrow">Mia is explaining</p>
        <h3>{content.title}</h3>
        <ul>
          {content.points.map((point) => (
            <li key={point}>{point}</li>
          ))}
        </ul>
      </div>
    </article>
  );
}

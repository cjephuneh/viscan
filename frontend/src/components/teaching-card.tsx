import { TEACHING_CARDS } from "@/lib/coach";

function Glyph({ art }: { art: string }) {
  const s = { fill: "none", stroke: "currentColor", strokeWidth: 2.2, strokeLinecap: "round" as const, strokeLinejoin: "round" as const };
  switch (art) {
    case "cervix":
      return (
        <>
          <circle cx="32" cy="32" r="22" {...s} />
          <ellipse cx="32" cy="32" rx="5" ry="3" fill="currentColor" />
          <path d="M40 18a16 16 0 0 1 8 10" {...s} strokeWidth={5} opacity="0.35" />
        </>
      );
    case "zones":
      return (
        <>
          <circle cx="32" cy="32" r="22" {...s} />
          <circle cx="32" cy="32" r="12" {...s} strokeDasharray="3 4" />
          <ellipse cx="32" cy="32" rx="4" ry="2.5" fill="currentColor" />
        </>
      );
    case "score":
      return <path d="M12 48V36M24 48V28M36 48V20M48 48V12" {...s} strokeWidth={5} />;
    case "check":
      return (
        <>
          <rect x="14" y="10" width="36" height="44" rx="5" {...s} />
          <path d="M21 24l4 4 7-8M21 40l4 4 7-8M37 26h7M37 42h7" {...s} />
        </>
      );
    case "treat":
      return <path d="M14 50l20-20M30 26l8-8 8 8-8 8zM46 12l6 6" {...s} />;
    case "refer":
      return <path d="M12 32h32M34 20l12 12-12 12M52 14v36" {...s} />;
    case "alert":
      return (
        <>
          <path d="M32 10l24 42H8z" {...s} />
          <path d="M32 26v12M32 45v1" {...s} />
        </>
      );
    case "talk":
      return <path d="M10 14h32v22H24l-8 8v-8h-6zM46 24h8v20h-5v6l-6-6H30v-4" {...s} />;
    case "calendar":
      return (
        <>
          <rect x="10" y="14" width="44" height="38" rx="5" {...s} />
          <path d="M10 26h44M22 8v10M42 8v10M22 38h6M36 38h6" {...s} />
        </>
      );
    case "shield":
      return <path d="M32 8l20 8v14c0 13-9 21-20 26-11-5-20-13-20-26V16z" {...s} />;
    case "camera":
      return (
        <>
          <rect x="8" y="18" width="48" height="32" rx="5" {...s} />
          <circle cx="32" cy="34" r="9" {...s} />
          <path d="M22 18l4-6h12l4 6" {...s} />
        </>
      );
    default:
      return (
        <>
          <rect x="14" y="14" width="36" height="36" rx="8" {...s} />
          <path d="M24 26h16M24 32h16M24 38h10M8 24h6M8 40h6M50 24h6M50 40h6" {...s} />
        </>
      );
  }
}

export function TeachingCard({ card }: { card: string }) {
  const content = TEACHING_CARDS[card];
  if (!content) return null;
  return (
    <article className="teaching-card">
      <div className="teaching-art" aria-hidden="true">
        <svg viewBox="0 0 64 64">
          <Glyph art={content.art} />
        </svg>
      </div>
      <div>
        <p className="eyebrow">Teaching card</p>
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

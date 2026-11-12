type ViscanMarkProps = {
  className?: string;
  size?: "sm" | "md" | "lg";
};

const SIZES = {
  sm: { width: 168, height: 48 },
  md: { width: 228, height: 62 },
  lg: { width: 276, height: 74 },
} as const;

/**
 * Magical brand mark: oversized V + clean "iscan" wordmark.
 */
export function ViscanMark({ className, size = "md" }: ViscanMarkProps) {
  const dims = SIZES[size];
  const uid = "viscanMark";

  return (
    <svg
      className={["viscan-logo", className].filter(Boolean).join(" ")}
      width={dims.width}
      height={dims.height}
      viewBox="0 0 210 72"
      fill="none"
      xmlns="http://www.w3.org/2000/svg"
      aria-hidden="true"
      focusable="false"
    >
      <defs>
        <linearGradient id={`${uid}-v`} x1="2" y1="8" x2="48" y2="64" gradientUnits="userSpaceOnUse">
          <stop stopColor="#fff4f9" />
          <stop offset="0.5" stopColor="#f7c1dc" />
          <stop offset="1" stopColor="#e7a0c8" />
        </linearGradient>
        <linearGradient id={`${uid}-rest`} x1="46" y1="18" x2="198" y2="54" gradientUnits="userSpaceOnUse">
          <stop stopColor="#fff0f6" />
          <stop offset="0.55" stopColor="#f3b7d4" />
          <stop offset="1" stopColor="#e7a0c8" />
        </linearGradient>
        <linearGradient id={`${uid}-sheen`} x1="4" y1="16" x2="200" y2="52" gradientUnits="userSpaceOnUse">
          <stop stopColor="#ffffff" stopOpacity="0" />
          <stop offset="0.4" stopColor="#ffffff" stopOpacity="0.5" />
          <stop offset="1" stopColor="#ffffff" stopOpacity="0" />
        </linearGradient>
        <linearGradient id={`${uid}-sweep`} x1="8" y1="62" x2="198" y2="62" gradientUnits="userSpaceOnUse">
          <stop stopColor="#f0b4d4" stopOpacity="0" />
          <stop offset="0.15" stopColor="#f0b4d4" />
          <stop offset="0.5" stopColor="#c45b93" />
          <stop offset="0.85" stopColor="#2f6b52" />
          <stop offset="1" stopColor="#2f6b52" stopOpacity="0" />
        </linearGradient>
        <radialGradient id={`${uid}-halo`} cx="28" cy="36" r="28" gradientUnits="userSpaceOnUse">
          <stop stopColor="#f8e8f3" stopOpacity="0.85" />
          <stop offset="1" stopColor="#f8e8f3" stopOpacity="0" />
        </radialGradient>
        <filter id={`${uid}-glow`} x="-25%" y="-25%" width="150%" height="150%">
          <feGaussianBlur stdDeviation="1.2" result="blur" />
          <feMerge>
            <feMergeNode in="blur" />
            <feMergeNode in="SourceGraphic" />
          </feMerge>
        </filter>
      </defs>

      {/* Soft halo behind the oversized V */}
      <ellipse cx="30" cy="38" rx="28" ry="24" fill={`url(#${uid}-halo)`} />

      <g filter={`url(#${uid}-glow)`}>
        {/* Wordmark: big V + cleaner iscan */}
        <text
          x="4"
          y="50"
          fontFamily="var(--font-display), var(--font-source-serif), Georgia, 'Times New Roman', serif"
          fontWeight="700"
          letterSpacing="-0.035em"
        >
          <tspan
            fill="var(--mark-ink)"
            fontSize="56"
            fontWeight="800"
            letterSpacing="-0.06em"
          >
            V
          </tspan>
          <tspan
            fill="var(--mark-ink)"
            fontSize="38"
            dx="-2"
            dy="-1"
            letterSpacing="-0.03em"
          >
            iscan
          </tspan>
        </text>

        {/* Light sheen across the word */}
        <rect
          x="4"
          y="18"
          width="190"
          height="36"
          fill={`url(#${uid}-sheen)`}
          opacity="0.32"
          style={{ mixBlendMode: "screen" }}
        />

        {/* Delicate arc over the V */}
        <path
          d="M10 18c10-11 24-13 36-7"
          stroke={`url(#${uid}-v)`}
          strokeWidth="1.8"
          strokeLinecap="round"
          fill="none"
          opacity="0.9"
        />

        {/* Spark accents */}
        <path
          d="M48 12l1.2 2.4 2.4 1.2-2.4 1.2L48 19l-1.2-2.4-2.4-1.2 2.4-1.2L48 12z"
          fill="#e7a0c8"
        />
        <path
          d="M118 16l0.9 1.8 1.8 0.9-1.8 0.9L118 21.4l-0.9-1.8-1.8-0.9 1.8-0.9L118 16z"
          fill="#2f6b52"
          opacity="0.9"
        />
        <path
          d="M178 26l0.75 1.5 1.5 0.75-1.5 0.75L178 30.5l-0.75-1.5-1.5-0.75 1.5-0.75L178 26z"
          fill="#c45b93"
          opacity="0.85"
        />

        {/* Tiny glow dots */}
        <circle cx="72" cy="56" r="1.15" fill="#e7a0c8" opacity="0.8" />
        <circle cx="142" cy="56" r="1.15" fill="#2f6b52" opacity="0.8" />
      </g>

      {/* Magical underline sweep */}
      <path
        d="M10 60c42 7 108 7 186 0"
        stroke={`url(#${uid}-sweep)`}
        strokeWidth="2.2"
        strokeLinecap="round"
      />
    </svg>
  );
}

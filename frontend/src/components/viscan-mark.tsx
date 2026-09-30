export function ViscanMark({ className }: { className?: string }) {
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

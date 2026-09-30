type Arc = { clock_start: number; clock_end: number; label?: string };

const CX = 100;
const CY = 100;

function point(hour: number, r: number) {
  const angle = ((hour % 12) / 12) * Math.PI * 2 - Math.PI / 2;
  return [CX + r * Math.cos(angle), CY + r * Math.sin(angle)];
}

function wedge(start: number, end: number, inner: number, outer: number) {
  const span = ((end - start + 12) % 12) || 12;
  const large = span > 6 ? 1 : 0;
  const [x1, y1] = point(start, outer);
  const [x2, y2] = point(start + span, outer);
  const [x3, y3] = point(start + span, inner);
  const [x4, y4] = point(start, inner);
  return `M${x1},${y1} A${outer},${outer} 0 ${large} 1 ${x2},${y2} L${x3},${y3} A${inner},${inner} 0 ${large} 0 ${x4},${y4} Z`;
}

export function CervixClock({ lesions, focus }: { lesions: Arc[]; focus?: Arc | null }) {
  const focusMatches = (l: Arc) => focus && l.clock_start === focus.clock_start && l.clock_end === focus.clock_end;
  const extra = focus && !lesions.some(focusMatches) ? [focus] : [];
  return (
    <figure className="cervix-clock">
      <svg viewBox="0 0 200 200" role="img" aria-label="Cervix clock face with lesion positions">
        <circle cx={CX} cy={CY} r="86" className="clock-cervix" />
        <circle cx={CX} cy={CY} r="46" className="clock-scj" />
        <ellipse cx={CX} cy={CY} rx="10" ry="6" className="clock-os" />
        {[...lesions, ...extra].map((l, i) => (
          <path
            key={`${l.clock_start}-${l.clock_end}-${i}`}
            d={wedge(l.clock_start, l.clock_end, 22, 78)}
            className={focusMatches(l) ? "clock-lesion focus" : "clock-lesion"}
          />
        ))}
        {Array.from({ length: 12 }, (_, i) => {
          const hour = i + 1;
          const [x, y] = point(hour, 96);
          return (
            <text key={hour} x={x} y={y} className="clock-hour" textAnchor="middle" dominantBaseline="middle">
              {hour}
            </text>
          );
        })}
      </svg>
      <figcaption>
        {focus
          ? `${focus.label ? `${focus.label}: ` : ""}${focus.clock_start} to ${focus.clock_end} o'clock`
          : lesions.length
            ? `${lesions.length} lesion${lesions.length > 1 ? "s" : ""} · dashed ring is the SCJ`
            : "No lesions marked · dashed ring is the SCJ"}
      </figcaption>
    </figure>
  );
}

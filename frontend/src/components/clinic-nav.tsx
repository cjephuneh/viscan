"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { ViscanMark } from "@/components/viscan-mark";

// MVP: two screens only. Clinician screening (with its care step) and patient check-in.
export const CLINIC_LINKS = [
  { href: "/", label: "Screening", match: ["/", "/care"] },
  { href: "/patient", label: "Patient check-in", match: ["/patient"] },
];

export function isActive(pathname: string, match: string[]) {
  return match.some((m) => (m === "/" ? pathname === "/" : pathname === m || pathname.startsWith(`${m}/`)));
}

export function ClinicNav() {
  const pathname = usePathname() ?? "";

  return (
    <header className="clinic-bar">
      <div className="clinic-bar-inner">
        <Link href="/" className="clinic-brand" aria-label="VISCAN screening">
          <span className="mark" aria-hidden="true">
            <ViscanMark />
          </span>
          <span>
            <strong>VISCAN</strong>
            <small>VIA screening</small>
          </span>
        </Link>
        <nav aria-label="Clinic">
          <ul className="clinic-links">
            {CLINIC_LINKS.map((link) => {
              const active = isActive(pathname, link.match);
              return (
                <li key={link.href}>
                  <Link href={link.href} className={active ? "on" : undefined} aria-current={active ? "page" : undefined}>
                    {link.label}
                  </Link>
                </li>
              );
            })}
          </ul>
        </nav>
      </div>
    </header>
  );
}

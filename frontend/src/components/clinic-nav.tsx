"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { ViscanMark } from "@/components/viscan-mark";

export const CLINIC_LINKS = [
  { href: "/dashboard", label: "Overview", match: ["/dashboard"] },
  { href: "/screening", label: "New screening", match: ["/screening"] },
  { href: "/screenings", label: "Past screenings", match: ["/screenings", "/care"] },
  { href: "/learn", label: "Training", match: ["/learn"] },
];

export function isActive(pathname: string, match: string[]) {
  return match.some((m) => pathname === m || pathname.startsWith(`${m}/`));
}

export function ClinicNav() {
  const pathname = usePathname() ?? "";

  return (
    <header className="clinic-bar">
      <div className="clinic-bar-inner">
        <Link href="/dashboard" className="clinic-brand" aria-label="VISCAN overview">
          <span className="mark" aria-hidden="true">
            <ViscanMark />
          </span>
          <span>
            <strong>VISCAN</strong>
            <small>Clinic workspace</small>
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
        <Link href="/patient" className="clinic-checkin">
          Patient check-in
        </Link>
      </div>
    </header>
  );
}

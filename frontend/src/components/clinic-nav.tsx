"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useState } from "react";
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
  const [menuOpen, setMenuOpen] = useState(false);

  useEffect(() => {
    setMenuOpen(false);
  }, [pathname]);

  useEffect(() => {
    if (!menuOpen) return;
    const onKey = (event: KeyboardEvent) => {
      if (event.key === "Escape") setMenuOpen(false);
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [menuOpen]);

  return (
    <header className={menuOpen ? "clinic-bar menu-open" : "clinic-bar"}>
      <div className="clinic-bar-inner">
        <Link href="/dashboard" className="clinic-brand" aria-label="VISCAN overview">
          <span className="brand-logo" aria-hidden="true">
            <ViscanMark size="lg" />
          </span>
          <span className="brand-meta">
            <small>Clinic workspace</small>
          </span>
        </Link>

        <button
          type="button"
          className="clinic-menu-toggle"
          aria-label={menuOpen ? "Close menu" : "Open menu"}
          aria-expanded={menuOpen}
          aria-controls="clinic-menu"
          onClick={() => setMenuOpen((open) => !open)}
        >
          {menuOpen ? (
            <span className="clinic-menu-close" aria-hidden="true">
              ×
            </span>
          ) : (
            <svg className="clinic-menu-icon" viewBox="0 0 24 24" aria-hidden="true" focusable="false">
              <path d="M4 7h16" />
              <path d="M4 12h16" />
              <path d="M4 17h16" />
            </svg>
          )}
        </button>

        <nav id="clinic-menu" aria-label="Clinic">
          <ul className="clinic-links">
            {CLINIC_LINKS.map((link) => {
              const active = isActive(pathname, link.match);
              return (
                <li key={link.href}>
                  <Link
                    href={link.href}
                    className={active ? "on" : undefined}
                    aria-current={active ? "page" : undefined}
                    onClick={() => setMenuOpen(false)}
                  >
                    {link.label}
                  </Link>
                </li>
              );
            })}
          </ul>
        </nav>

        <Link href="/patient" className="clinic-checkin" aria-label="Patient check-in">
          Patient check-in
        </Link>
      </div>
    </header>
  );
}

export function ClinicFooter() {
  const year = new Date().getFullYear();

  return (
    <footer className="clinic-footer">
      <div className="clinic-footer-inner">
        <p>
          © {year} VISCAN · Clinic workspace for VIA cervical screening. Confirm every AI reading before care
          decisions.
        </p>
      </div>
    </footer>
  );
}

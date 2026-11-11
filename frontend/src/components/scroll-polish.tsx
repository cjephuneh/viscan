"use client";

import { useEffect } from "react";

/**
 * Light scroll polish only — toggles html.is-scrolled for CSS magic.
 * Does not change app functionality.
 */
export function ScrollPolish() {
  useEffect(() => {
    const root = document.documentElement;
    let ticking = false;

    const update = () => {
      ticking = false;
      root.classList.toggle("is-scrolled", window.scrollY > 10);
    };

    const onScroll = () => {
      if (ticking) return;
      ticking = true;
      window.requestAnimationFrame(update);
    };

    update();
    window.addEventListener("scroll", onScroll, { passive: true });
    return () => window.removeEventListener("scroll", onScroll);
  }, []);

  return null;
}

"use client";

import "leaflet/dist/leaflet.css";
import { useEffect, useRef } from "react";
import type { Map as LeafletMap, LayerGroup } from "leaflet";
import type { PartnerHospital, Pharmacy } from "@/lib/viscan";

export type Selected = { kind: "pharmacy" | "hospital"; id: string | number } | null;

const COLORS = { patient: "#2d5f8a", pharmacy: "#2f7d5b", hospital: "#b5473a" };

export function CareMap({
  center,
  radius,
  pharmacies,
  hospitals,
  selected,
}: {
  center: { lat: number; lng: number };
  radius: number;
  pharmacies: Pharmacy[];
  hospitals: PartnerHospital[];
  selected: Selected;
}) {
  const elementRef = useRef<HTMLDivElement>(null);
  const mapRef = useRef<LeafletMap | null>(null);
  const layerRef = useRef<LayerGroup | null>(null);
  const leafletRef = useRef<typeof import("leaflet") | null>(null);

  useEffect(() => {
    let cancelled = false;
    import("leaflet").then((L) => {
      if (cancelled || !elementRef.current || mapRef.current) return;
      leafletRef.current = L;
      const map = L.map(elementRef.current, { scrollWheelZoom: false }).setView([center.lat, center.lng], 14);
      L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
        maxZoom: 19,
        attribution: "&copy; OpenStreetMap contributors",
      }).addTo(map);
      mapRef.current = map;
      layerRef.current = L.layerGroup().addTo(map);
      draw();
    });
    return () => {
      cancelled = true;
      mapRef.current?.remove();
      mapRef.current = null;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  function draw() {
    const L = leafletRef.current;
    const map = mapRef.current;
    const layer = layerRef.current;
    if (!L || !map || !layer) return;
    layer.clearLayers();

    L.circle([center.lat, center.lng], {
      radius,
      color: COLORS.patient,
      weight: 1,
      fillOpacity: 0.04,
    }).addTo(layer);
    L.circleMarker([center.lat, center.lng], {
      radius: 8,
      color: "#fff",
      weight: 2,
      fillColor: COLORS.patient,
      fillOpacity: 1,
    })
      .bindTooltip("Screening location")
      .addTo(layer);

    const points: [number, number][] = [[center.lat, center.lng]];
    for (const p of pharmacies) {
      const on = selected?.kind === "pharmacy" && selected.id === p.id;
      L.circleMarker([p.latitude, p.longitude], {
        radius: on ? 9 : 6,
        color: "#fff",
        weight: on ? 3 : 1.5,
        fillColor: COLORS.pharmacy,
        fillOpacity: 0.95,
      })
        .bindTooltip(`${p.name} · ${p.distance_km} km`)
        .addTo(layer);
      points.push([p.latitude, p.longitude]);
    }
    for (const h of hospitals) {
      const on = selected?.kind === "hospital" && selected.id === h.id;
      L.circleMarker([h.latitude, h.longitude], {
        radius: on ? 11 : 8,
        color: "#fff",
        weight: on ? 3 : 2,
        fillColor: COLORS.hospital,
        fillOpacity: 1,
      })
        .bindTooltip(`${h.name} · partner hospital`)
        .addTo(layer);
      points.push([h.latitude, h.longitude]);
    }

    const focus =
      selected?.kind === "pharmacy"
        ? pharmacies.find((p) => p.id === selected.id)
        : selected?.kind === "hospital"
          ? hospitals.find((h) => h.id === selected.id)
          : undefined;
    if (focus) map.setView([focus.latitude, focus.longitude], 16);
    else if (points.length > 1) map.fitBounds(L.latLngBounds(points), { padding: [24, 24], maxZoom: 15 });
  }

  useEffect(draw);

  return (
    <div className="care-map-wrap">
      <div ref={elementRef} className="care-map" role="img" aria-label="Map of nearby pharmacies and partner hospitals" />
      <ul className="map-legend" aria-hidden="true">
        <li><span style={{ background: COLORS.patient }} />Screening location</li>
        <li><span style={{ background: COLORS.pharmacy }} />Pharmacy</li>
        <li><span style={{ background: COLORS.hospital }} />Partner hospital</li>
      </ul>
    </div>
  );
}

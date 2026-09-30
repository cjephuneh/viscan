"use client";

import dynamic from "next/dynamic";
import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import type { Selected } from "@/components/care-map";
import { SendResults } from "@/components/send-results";
import {
  type CareSummary,
  type PartnerHospital,
  type Pharmacy,
  getCare,
  getPartnerHospitals,
  getPharmacies,
  humanize,
  referPatient,
} from "@/lib/viscan";

const CareMap = dynamic(() => import("@/components/care-map").then((m) => m.CareMap), {
  ssr: false,
  loading: () => <div className="care-map placeholder">Loading map…</div>,
});

const RADII = [1000, 2000, 5000, 10000];

type Center = { lat: number; lng: number; source: "device" | "clinic" };

function directionsUrl(lat: number, lng: number, from: Center) {
  return `https://www.google.com/maps/dir/?api=1&origin=${from.lat},${from.lng}&destination=${lat},${lng}`;
}

export function CareScreen({ interpretationId }: { interpretationId: number }) {
  const [care, setCare] = useState<CareSummary | null>(null);
  const [careError, setCareError] = useState("");
  const [center, setCenter] = useState<Center | null>(null);
  const [radius, setRadius] = useState(2000);
  const [hospitals, setHospitals] = useState<PartnerHospital[]>([]);
  const [pharmacyResult, setPharmacyResult] = useState<{ key: string; results: Pharmacy[]; error: string }>({
    key: "",
    results: [],
    error: "",
  });
  const [selected, setSelected] = useState<Selected>(null);
  const [referredBy, setReferredBy] = useState("");
  const [referring, setReferring] = useState<number | null>(null);
  const [referError, setReferError] = useState("");
  const [refreshKey, setRefreshKey] = useState(0);

  const loadCare = useCallback(() => {
    getCare(interpretationId)
      .then(setCare)
      .catch((err: Error) => setCareError(err.message));
  }, [interpretationId]);

  useEffect(loadCare, [loadCare]);

  useEffect(() => {
    let active = true;
    const fallbackToClinic = () =>
      getPartnerHospitals()
        .then((data) => active && setCenter({ ...data.center, source: "clinic" }))
        .catch(() => active && setCenter({ lat: -1.9441, lng: 30.0619, source: "clinic" }));

    if (typeof navigator === "undefined" || !navigator.geolocation) {
      fallbackToClinic();
    } else {
      navigator.geolocation.getCurrentPosition(
        (pos) => active && setCenter({ lat: pos.coords.latitude, lng: pos.coords.longitude, source: "device" }),
        () => fallbackToClinic(),
        { timeout: 8000, maximumAge: 600000 },
      );
    }
    return () => {
      active = false;
    };
  }, []);

  useEffect(() => {
    if (!center) return;
    getPartnerHospitals(center.lat, center.lng)
      .then((data) => setHospitals(data.results))
      .catch(() => setHospitals([]));
  }, [center]);

  useEffect(() => {
    if (!center) return;
    let active = true;
    const key = `${center.lat},${center.lng},${radius}`;
    getPharmacies(center.lat, center.lng, radius)
      .then((data) => active && setPharmacyResult({ key, results: data.results, error: "" }))
      .catch(
        (err: Error) =>
          active && setPharmacyResult({ key, results: [], error: err.message || "Pharmacy search is unavailable right now." }),
      );
    return () => {
      active = false;
    };
  }, [center, radius]);

  async function refer(hospital: PartnerHospital) {
    setReferError("");
    setReferring(hospital.id);
    try {
      await referPatient(interpretationId, hospital.id, referredBy.trim() || undefined);
      loadCare();
      setRefreshKey((k) => k + 1);
    } catch (err) {
      setReferError((err as Error).message);
    } finally {
      setReferring(null);
    }
  }

  const pharmacyKey = center ? `${center.lat},${center.lng},${radius}` : "";
  const pharmacyState: "idle" | "loading" | "error" =
    !center || pharmacyResult.key !== pharmacyKey ? "loading" : pharmacyResult.error ? "error" : "idle";
  const pharmacies = pharmacyState === "idle" ? pharmacyResult.results : [];
  const pharmacyError = pharmacyResult.error;

  const referredIds = new Set(care?.referrals.map((r) => r.hospital.id));
  const tone = care?.is_suspicious ? "alert" : "clear";

  return (
    <div className="page care-page">
      <div className="atmosphere" aria-hidden="true" />

      <header className="care-header">
        <Link href="/" className="back-link">
          ← Back to screening
        </Link>
        <p className="eyebrow">After the screen</p>
        <h1 className="care-title">Referral &amp; nearby care</h1>
        {careError ? <p className="error">{careError}</p> : null}
        {care ? (
          <div className={`care-summary verdict ${tone}`}>
            <p className="verdict-label">
              {care.patient_external_id ? `Patient ${care.patient_external_id} · ` : ""}
              {care.result_source === "clinician" ? "Clinician-confirmed" : "AI reading, not yet confirmed"}
            </p>
            <p className="classification">{humanize(care.final_via_result)}</p>
            <p className="summary">{care.action}</p>
            {care.needs_referral ? (
              <p className="care-flag">Referral recommended{care.urgency ? ` · ${humanize(care.urgency)}` : ""}</p>
            ) : null}
          </div>
        ) : null}
      </header>

      <div className="care-grid">
        <section className="panel map-panel" aria-labelledby="map-title">
          <div className="panel-head">
            <div>
              <p className="eyebrow">Map</p>
              <h2 id="map-title">Around the patient</h2>
            </div>
            <label className="field radius-field">
              <span>Search radius</span>
              <select value={radius} onChange={(event) => setRadius(Number(event.target.value))}>
                {RADII.map((r) => (
                  <option key={r} value={r}>
                    {r / 1000} km
                  </option>
                ))}
              </select>
            </label>
          </div>
          {center ? (
            <>
              <CareMap center={center} radius={radius} pharmacies={pharmacies} hospitals={hospitals} selected={selected} />
              <p className="quiet">
                {center.source === "device"
                  ? "Centred on this device's location."
                  : "Location unavailable, so the map is centred on the clinic's default location."}
              </p>
            </>
          ) : (
            <div className="care-map placeholder">Finding your location…</div>
          )}
        </section>

        <section className="panel" aria-labelledby="partners-title">
          <div className="panel-head">
            <div>
              <p className="eyebrow">Refer</p>
              <h2 id="partners-title">Partner hospitals</h2>
            </div>
            <p className="panel-status">{hospitals.length} available</p>
          </div>
          <label className="field">
            <span>Referred by</span>
            <input
              value={referredBy}
              onChange={(event) => setReferredBy(event.target.value)}
              placeholder="Your clinician ID"
            />
          </label>
          {referError ? <p className="error">{referError}</p> : null}
          <ul className="place-list">
            {hospitals.map((h) => (
              <li
                key={h.id}
                className={selected?.kind === "hospital" && selected.id === h.id ? "place on" : "place"}
              >
                <button type="button" className="place-main" onClick={() => setSelected({ kind: "hospital", id: h.id })}>
                  <strong>{h.name}</strong>
                  <span>
                    {h.distance_km} km{h.opening_hours ? ` · ${h.opening_hours}` : ""}
                  </span>
                  <span className="tags">
                    {h.services.map((s) => (
                      <em key={s}>{s}</em>
                    ))}
                    {h.is_demo ? <em className="demo">demo</em> : null}
                  </span>
                </button>
                <div className="place-actions">
                  {referredIds.has(h.id) ? (
                    <span className="referred">Referred ✓</span>
                  ) : (
                    <button
                      type="button"
                      className="primary small"
                      disabled={referring !== null}
                      onClick={() => refer(h)}
                      aria-label={`Refer to ${h.name}`}
                    >
                      {referring === h.id ? "Referring…" : "Refer"}
                    </button>
                  )}
                  {center ? (
                    <a href={directionsUrl(h.latitude, h.longitude, center)} target="_blank" rel="noreferrer">
                      Directions
                    </a>
                  ) : null}
                </div>
              </li>
            ))}
          </ul>
          {care?.referrals.length ? (
            <div className="result-block">
              <h3 className="block-title">Referrals made</h3>
              <ul className="sent-list">
                {care.referrals.map((r) => (
                  <li key={r.id}>
                    <strong>{r.hospital.name}</strong> · {humanize(r.urgency)} · {r.status}
                  </li>
                ))}
              </ul>
            </div>
          ) : null}
        </section>

        <section className="panel" aria-labelledby="pharm-title">
          <div className="panel-head">
            <div>
              <p className="eyebrow">Supplies</p>
              <h2 id="pharm-title">Nearby pharmacies</h2>
            </div>
            <p className="panel-status">
              {pharmacyState === "loading" ? "Searching…" : `${pharmacies.length} within ${radius / 1000} km`}
            </p>
          </div>

          {care?.suggested_supplies.length ? (
            <div className="result-block">
              <h3 className="block-title">Suggested items</h3>
              <ul className="supplies">
                {care.suggested_supplies.map((s) => (
                  <li key={s.item}>
                    <strong>{s.item}</strong>
                    <span>{s.why}</span>
                    {s.prescription ? <em>Prescription only</em> : null}
                  </li>
                ))}
              </ul>
            </div>
          ) : null}

          {pharmacyState === "error" ? (
            <p className="error">{pharmacyError || "Pharmacy search is unavailable right now."}</p>
          ) : null}
          {pharmacyState === "idle" && !pharmacies.length && center ? (
            <p className="quiet">No pharmacies found in this radius. Try a wider search.</p>
          ) : null}
          <ul className="place-list">
            {pharmacies.map((p) => (
              <li
                key={p.id}
                className={selected?.kind === "pharmacy" && selected.id === p.id ? "place on" : "place"}
              >
                <button type="button" className="place-main" onClick={() => setSelected({ kind: "pharmacy", id: p.id })}>
                  <strong>{p.name}</strong>
                  <span>
                    {p.distance_km} km
                    {p.opening_hours ? ` · ${p.opening_hours}` : ""}
                    {p.phone ? ` · ${p.phone}` : ""}
                  </span>
                  {p.address ? <span>{p.address}</span> : null}
                </button>
                <div className="place-actions">
                  {center ? (
                    <a href={directionsUrl(p.latitude, p.longitude, center)} target="_blank" rel="noreferrer">
                      Directions
                    </a>
                  ) : null}
                </div>
              </li>
            ))}
          </ul>
          <p className="footnote">Pharmacy data © OpenStreetMap contributors. Check opening hours before sending a patient.</p>
        </section>

        <section className="panel" aria-label="Send results">
          <SendResults interpretationId={interpretationId} sentBy={referredBy.trim()} refreshKey={refreshKey} />
        </section>
      </div>
    </div>
  );
}

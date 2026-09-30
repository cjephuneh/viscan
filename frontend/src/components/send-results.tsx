"use client";

import { useEffect, useState } from "react";
import { type Channel, type NotificationRecord, getCare, sendResults } from "@/lib/viscan";

const CHANNELS: { id: Channel; label: string }[] = [
  { id: "sms", label: "SMS" },
  { id: "whatsapp", label: "WhatsApp" },
];

export function SendResults({
  interpretationId,
  sentBy,
  refreshKey = 0,
  defaultPhone,
  defaultChannel,
}: {
  interpretationId: number;
  sentBy?: string;
  refreshKey?: number;
  defaultPhone?: string | null;
  defaultChannel?: Channel | null;
}) {
  const [channel, setChannel] = useState<Channel>(defaultChannel ?? "sms");
  const [phone, setPhone] = useState(defaultPhone ?? "");
  const [previews, setPreviews] = useState<Record<Channel, string> | null>(null);
  const [draft, setDraft] = useState<string | null>(null);
  const [sending, setSending] = useState(false);
  const [error, setError] = useState("");
  const [sent, setSent] = useState<NotificationRecord[]>([]);

  useEffect(() => {
    let active = true;
    getCare(interpretationId)
      .then((care) => {
        if (!active) return;
        setPreviews(care.message_preview);
        setSent(care.notifications);
      })
      .catch(() => active && setPreviews(null));
    return () => {
      active = false;
    };
  }, [interpretationId, refreshKey]);

  const message = draft ?? previews?.[channel] ?? "";

  async function send() {
    if (phone.replace(/\D/g, "").length < 7) {
      setError("Enter the patient's phone number, including the country code.");
      return;
    }
    setError("");
    setSending(true);
    try {
      const record = await sendResults(interpretationId, { channel, phone, message, sent_by: sentBy });
      setSent((items) => [...items, record]);
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setSending(false);
    }
  }

  return (
    <section className="send-results" aria-labelledby={`send-${interpretationId}`}>
      <div className="send-head">
        <h3 id={`send-${interpretationId}`} className="block-title">
          Send results to the patient
        </h3>
        <span className="demo-badge">Demo · not actually sent</span>
      </div>

      <div className="channel-switch" role="group" aria-label="Channel">
        {CHANNELS.map((c) => (
          <button
            key={c.id}
            type="button"
            className={channel === c.id ? "on" : ""}
            aria-pressed={channel === c.id}
            onClick={() => setChannel(c.id)}
          >
            {c.label}
          </button>
        ))}
      </div>

      <label className="field">
        <span>Patient phone</span>
        <input
          value={phone}
          onChange={(event) => setPhone(event.target.value)}
          placeholder="+250 788 000 000"
          inputMode="tel"
        />
      </label>

      <label className="field notes-field">
        <span className="note-label">Message</span>
        <textarea
          className="notes"
          value={message}
          onChange={(event) => setDraft(event.target.value)}
          rows={4}
        />
      </label>

      {error ? <p className="error">{error}</p> : null}

      <div className="actions">
        <button type="button" className="primary" onClick={send} disabled={sending || !message.trim()}>
          {sending ? "Sending…" : `Send by ${channel === "sms" ? "SMS" : "WhatsApp"}`}
        </button>
      </div>

      {sent.length ? (
        <ul className="sent-list" aria-label="Messages sent">
          {sent.map((n) => (
            <li key={n.id}>
              <strong>{n.channel === "sms" ? "SMS" : "WhatsApp"}</strong> to {n.recipient} ·{" "}
              <span className="demo-status">{n.status}</span>
            </li>
          ))}
        </ul>
      ) : null}
    </section>
  );
}

"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import type { AnamClient } from "@anam-ai/js-sdk";

export type AvatarStatus = "idle" | "connecting" | "live" | "ended" | "error";
export type ChatLine = { role: "user" | "persona"; content: string };
export type ToolHandlers = Record<string, (args: Record<string, unknown>) => Promise<string>>;

export function useAnamAvatar(videoId: string) {
  const clientRef = useRef<AnamClient | null>(null);
  const sessionIdRef = useRef<string | null>(null);
  const historyRef = useRef<ChatLine[]>([]);
  const captionIdRef = useRef<string | null>(null);
  const [status, setStatus] = useState<AvatarStatus>("idle");
  const [error, setError] = useState("");
  const [caption, setCaption] = useState("");
  const [speaking, setSpeaking] = useState(false);
  const [listening, setListening] = useState(false);
  const [muted, setMuted] = useState(false);
  const [history, setHistory] = useState<ChatLine[]>([]);

  const start = useCallback(
    async (sessionToken: string, tools: ToolHandlers) => {
      setStatus("connecting");
      setError("");
      try {
        const { createClient, AnamEvent, ConnectionClosedCode } = await import("@anam-ai/js-sdk");
        const client = createClient(sessionToken);
        clientRef.current = client;

        for (const [name, run] of Object.entries(tools)) {
          client.registerToolCallHandler(name, {
            onStart: async (payload) => {
              try {
                return await run(payload.arguments ?? {});
              } catch {
                return "Noted.";
              }
            },
          });
        }

        client.addListener(AnamEvent.SESSION_READY, (id) => {
          sessionIdRef.current = id;
        });
        client.addListener(AnamEvent.VIDEO_PLAY_STARTED, () => setStatus("live"));
        client.addListener(AnamEvent.MESSAGE_STREAM_EVENT_RECEIVED, (event) => {
          if (event.role !== "persona") return;
          setSpeaking(!event.endOfSpeech);
          const fresh = captionIdRef.current !== event.id;
          captionIdRef.current = event.id;
          setCaption((current) => (fresh ? event.content : current + event.content));
        });
        client.addListener(AnamEvent.MESSAGE_HISTORY_UPDATED, (messages) => {
          const lines = messages.map((m) => ({ role: m.role, content: m.content }) as ChatLine);
          historyRef.current = lines;
          setHistory(lines);
          setSpeaking(false);
        });
        client.addListener(AnamEvent.USER_SPEECH_STARTED, () => {
          setListening(true);
          setCaption("");
        });
        client.addListener(AnamEvent.USER_SPEECH_ENDED, () => setListening(false));
        client.addListener(AnamEvent.MIC_PERMISSION_DENIED, () => {
          setError("Microphone access was blocked. You can still type your answers below.");
        });
        client.addListener(AnamEvent.CONNECTION_CLOSED, (reason, details) => {
          clientRef.current = null;
          setSpeaking(false);
          const normal = reason === ConnectionClosedCode.NORMAL;
          setStatus((current) => (current === "ended" || normal ? "ended" : "error"));
          if (reason === ConnectionClosedCode.MICROPHONE_PERMISSION_DENIED) {
            setError("Mia needs your microphone to hear you. You can answer by typing instead.");
          } else if (!normal) {
            setError(details || "The connection to Mia was lost.");
          }
        });

        const video = document.getElementById(videoId) as HTMLVideoElement | null;
        video?.addEventListener("playing", () => setStatus((s) => (s === "connecting" ? "live" : s)), { once: true });
        await client.streamToVideoElement(videoId);
        if (video && !video.paused && video.readyState >= 2) setStatus((s) => (s === "connecting" ? "live" : s));
      } catch (err) {
        clientRef.current = null;
        setStatus("error");
        setError((err as Error).message || "Could not connect to Mia.");
      }
    },
    [videoId],
  );

  const stop = useCallback(async () => {
    const client = clientRef.current;
    clientRef.current = null;
    setStatus("ended");
    setSpeaking(false);
    if (client) await client.stopStreaming().catch(() => undefined);
  }, []);

  const say = useCallback((text: string) => {
    const client = clientRef.current;
    if (!client || !text.trim()) return false;
    client.sendUserMessage(text.trim());
    const lines = [...historyRef.current, { role: "user" as const, content: text.trim() }];
    historyRef.current = lines;
    setHistory(lines);
    return true;
  }, []);

  const toggleMute = useCallback(() => {
    const client = clientRef.current;
    if (!client) return;
    if (client.getInputAudioState().isMuted) {
      client.unmuteInputAudio();
      setMuted(false);
    } else {
      client.muteInputAudio();
      setMuted(true);
    }
  }, []);

  useEffect(() => {
    return () => {
      clientRef.current?.stopStreaming().catch(() => undefined);
      clientRef.current = null;
    };
  }, []);

  return {
    status,
    error,
    caption,
    speaking,
    listening,
    muted,
    history,
    historyRef,
    sessionIdRef,
    start,
    stop,
    say,
    toggleMute,
  };
}

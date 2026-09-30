import { act, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { WelcomeScreen } from "@/components/welcome-screen";
import type { Intake } from "@/lib/intake";
import { intakeFixture } from "./fixtures";

type Handler = { onStart: (payload: { arguments: Record<string, unknown> }) => Promise<string> };

const sdk = vi.hoisted(() => ({
  handlers: {} as Record<string, Handler>,
  listeners: {} as Record<string, (...args: unknown[]) => void>,
  sent: [] as string[],
  stopped: false,
}));

vi.mock("@anam-ai/js-sdk", () => ({
  AnamEvent: {
    SESSION_READY: "SESSION_READY",
    VIDEO_PLAY_STARTED: "VIDEO_PLAY_STARTED",
    MESSAGE_STREAM_EVENT_RECEIVED: "MESSAGE_STREAM_EVENT_RECEIVED",
    MESSAGE_HISTORY_UPDATED: "MESSAGE_HISTORY_UPDATED",
    USER_SPEECH_STARTED: "USER_SPEECH_STARTED",
    USER_SPEECH_ENDED: "USER_SPEECH_ENDED",
    MIC_PERMISSION_DENIED: "MIC_PERMISSION_DENIED",
    CONNECTION_CLOSED: "CONNECTION_CLOSED",
  },
  ConnectionClosedCode: { NORMAL: "NORMAL", MICROPHONE_PERMISSION_DENIED: "MIC" },
  createClient: () => ({
    registerToolCallHandler: (name: string, handler: Handler) => {
      sdk.handlers[name] = handler;
    },
    addListener: (event: string, fn: (...args: unknown[]) => void) => {
      sdk.listeners[event] = fn;
    },
    streamToVideoElement: async () => {
      sdk.listeners.SESSION_READY?.("anam-session-1");
      sdk.listeners.VIDEO_PLAY_STARTED?.();
    },
    sendUserMessage: (text: string) => sdk.sent.push(text),
    stopStreaming: async () => {
      sdk.stopped = true;
    },
    getInputAudioState: () => ({ isMuted: false }),
    muteInputAudio: () => ({ isMuted: true }),
    unmuteInputAudio: () => ({ isMuted: false }),
  }),
}));

const blank: Intake = {
  ...intakeFixture,
  status: "in_progress",
  full_name: null,
  preferred_name: null,
  age: null,
  sex: null,
  answers: {},
  feelings: [],
  anxiety: { start: null, end: null, change: null },
  concerns: [],
  topics_covered: [],
  breathing_exercises: 0,
  summary: null,
};

const json = (body: unknown, status = 200) =>
  new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } });

function mockApi({ tokenStatus = 200 } = {}) {
  let intake = { ...blank };
  const fn = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
    const url = String(input);
    if (url === "/api/v1/avatar/persona") return json({ available: true, name: "Mia", image_url: null });
    if (url === "/api/v1/intake") return json(intake, 201);
    if (url.endsWith("/avatar-token"))
      return tokenStatus === 200
        ? json({ session_token: "tok", persona: { name: "Mia", image_url: null } })
        : json({ error: "The avatar is not configured." }, tokenStatus);
    if (url.endsWith("/events")) {
      const { type, data } = JSON.parse(String(init?.body));
      if (type === "details") intake = { ...intake, ...data };
      if (type === "feeling") intake = { ...intake, feelings: [...intake.feelings, data], anxiety: { start: intake.anxiety.start ?? data.level, end: data.level, change: null } };
      if (type === "topic") intake = { ...intake, topics_covered: [...intake.topics_covered, data.topic] };
      if (type === "answer") intake = { ...intake, answers: { ...intake.answers, [data.question]: { value: data.value, said: data.value, at: "" } } };
      if (type === "finish") intake = { ...intake, status: "completed" };
      return json({ message: type === "finish" ? `Intake complete. The patient's check-in code is ${intake.code}.` : "Saved.", intake });
    }
    return json({ error: "not found" }, 404);
  });
  vi.stubGlobal("fetch", fn);
  return fn;
}

const tool = (name: string, args: Record<string, unknown>) =>
  act(async () => {
    await sdk.handlers[name].onStart({ arguments: args });
  });

describe("WelcomeScreen", () => {
  let fetchMock: ReturnType<typeof mockApi>;

  beforeEach(() => {
    sdk.handlers = {};
    sdk.listeners = {};
    sdk.sent = [];
    sdk.stopped = false;
    fetchMock = mockApi();
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("introduces Mia honestly before the screening", async () => {
    render(<WelcomeScreen />);
    expect(screen.getByRole("heading", { level: 1 })).toHaveTextContent("Meet Mia, your guide for today.");
    expect(screen.getByText(/A real nurse\s+does the check itself/)).toBeInTheDocument();
    expect(await screen.findByRole("button", { name: "Meet Mia" })).toBeEnabled();
  });

  it("runs the avatar check-in: saves details, shows topics and breathing, ends with a code", async () => {
    render(<WelcomeScreen />);
    fireEvent.click(await screen.findByRole("button", { name: "Meet Mia" }));
    expect(await screen.findByText("Your turn: just speak")).toBeInTheDocument();
    expect(Object.keys(sdk.handlers)).toEqual(
      expect.arrayContaining(["save_patient_details", "save_answer", "record_feeling", "finish_intake"]),
    );

    await tool("save_patient_details", { full_name: "Grace Uwase", preferred_name: "Grace", age: 38, sex: "female" });
    expect(screen.getByRole("heading", { name: "Hi, Grace" })).toBeInTheDocument();
    const details = fetchMock.mock.calls.find(([u]) => String(u).endsWith("/events"))!;
    expect(JSON.parse(String(details[1]!.body))).toMatchObject({
      type: "details",
      data: { preferred_name: "Grace", age: 38 },
      anam_session_id: "anam-session-1",
    });

    await tool("record_feeling", { level: 5, note: "scared" });
    expect(screen.getByText("Very nervous")).toBeInTheDocument();

    await tool("show_topic", { topic: "what_to_expect" });
    expect(screen.getByRole("heading", { name: "What to expect" })).toBeInTheDocument();

    await tool("start_breathing_exercise", { rounds: 2 });
    expect(screen.getByRole("dialog", { name: "Breathing exercise" })).toBeInTheDocument();
    expect(screen.getByText("Round 1 of 2")).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "I'm feeling nervous" }));
    expect(sdk.sent).toContain("I'm feeling a bit nervous about this.");

    await tool("save_answer", { question: "pregnant", value: "no" });
    expect(screen.getByText("Could be pregnant")).toBeInTheDocument();

    await tool("record_feeling", { level: 2 });
    await tool("finish_intake", { summary: "Calmer now." });
    expect(screen.getAllByLabelText(/Check-in code K 7 M 3 Q/).length).toBeGreaterThan(0);

    fireEvent.click(screen.getByRole("button", { name: "Finish" }));
    expect(await screen.findByRole("heading", { name: "Thank you, Grace." })).toBeInTheDocument();
    expect(sdk.stopped).toBe(true);
    expect(screen.getByRole("link", { name: "Staff: open screening" })).toHaveAttribute("href", "/?intake=5");
  });

  it("falls back to the short form when the avatar is unavailable", async () => {
    fetchMock = mockApi({ tokenStatus: 503 });
    render(<WelcomeScreen />);
    fireEvent.click(await screen.findByRole("button", { name: "Meet Mia" }));
    expect(await screen.findByText(/let's use a short form instead/)).toBeInTheDocument();

    fireEvent.change(screen.getByRole("textbox", { name: "What's your name?" }), { target: { value: "Grace Uwase" } });
    fireEvent.click(screen.getByRole("button", { name: "Continue" }));
    await waitFor(() => expect(screen.getByRole("heading", { name: "Hi, Grace" })).toBeInTheDocument());
    expect(screen.getByRole("heading", { name: "How old are you?" })).toBeInTheDocument();
  });
});

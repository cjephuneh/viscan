import { act, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { CoachPanel } from "@/components/coach-panel";
import type { CoachSession } from "@/lib/coach";
import { interpretationFixture } from "./fixtures";

type Handler = { onStart: (payload: { arguments: Record<string, unknown> }) => Promise<string> };

const sdk = vi.hoisted(() => ({
  handlers: {} as Record<string, Handler>,
  listeners: {} as Record<string, (...args: unknown[]) => void>,
  sent: [] as string[],
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
      sdk.listeners.SESSION_READY?.("anam-coach-1");
      sdk.listeners.VIDEO_PLAY_STARTED?.();
    },
    sendUserMessage: (text: string) => sdk.sent.push(text),
    stopStreaming: async () => undefined,
    getInputAudioState: () => ({ isMuted: false }),
    muteInputAudio: () => ({ isMuted: true }),
    unmuteInputAudio: () => ({ isMuted: false }),
  }),
}));

const json = (body: unknown, status = 200) =>
  new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } });

function mockApi() {
  let session: CoachSession = {
    id: 3,
    interpretation_id: 7,
    clinician_id: "nurse-07",
    status: "active",
    topics: [],
    quiz: [],
    score: { asked: 0, answered: 0, correct: 0 },
    action_plan: [],
    roleplays: [],
    summary: null,
    created_at: "",
    ended_at: null,
  };
  const fn = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
    const url = String(input);
    if (url === "/api/v1/coach/persona") return json({ available: true, name: "Kezia", image_url: null });
    if (url === "/api/v1/coach/sessions") return json(session, 201);
    if (url.endsWith("/token")) return json({ session_token: "tok", persona: { name: "Kezia", image_url: null } });
    if (url.endsWith("/events")) {
      const { type, data } = JSON.parse(String(init?.body));
      if (type === "quiz_asked") session = { ...session, quiz: [...session.quiz, { ...data, explanation: data.explanation ?? "", chosen_index: null, correct: null }] };
      if (type === "quiz_answer") {
        const last = session.quiz.at(-1)!;
        const correct = data.chosen_index === last.correct_index;
        session = { ...session, quiz: [...session.quiz.slice(0, -1), { ...last, chosen_index: data.chosen_index, correct }], score: { asked: 1, answered: 1, correct: correct ? 1 : 0 } };
      }
      if (type === "action_step") session = { ...session, action_plan: [...session.action_plan, { step: data.step, why: data.why ?? "", done: false }] };
      if (type === "action_done") session = { ...session, action_plan: session.action_plan.map((s, i) => (i === data.index ? { ...s, done: data.done } : s)) };
      if (type === "roleplay_start") session = { ...session, roleplays: [{ scenario: data.scenario, strengths: [], improve: null }] };
      if (type === "roleplay_end") session = { ...session, roleplays: [{ ...session.roleplays[0], strengths: data.strengths, improve: data.improve }] };
      return json({ message: "Saved.", session });
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

describe("CoachPanel", () => {
  let fetchMock: ReturnType<typeof mockApi>;

  beforeEach(() => {
    sdk.handlers = {};
    sdk.listeners = {};
    sdk.sent = [];
    fetchMock = mockApi();
    Element.prototype.scrollIntoView = vi.fn();
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("teaches on the case: highlights sections, quizzes, builds a plan and role-plays", async () => {
    render(
      <>
        <section data-coach="eligibility">Ablation checklist</section>
        <CoachPanel interpretation={interpretationFixture} clinicianId="nurse-07" />
      </>,
    );
    fireEvent.click(await screen.findByRole("button", { name: "Start lesson with Kezia" }));
    expect(await screen.findByText("Ask anything")).toBeInTheDocument();
    const start = fetchMock.mock.calls.find(([u]) => String(u) === "/api/v1/coach/sessions")!;
    expect(JSON.parse(String(start[1]!.body))).toEqual({ interpretation_id: 7, clinician_id: "nurse-07" });

    await tool("highlight_section", { section: "eligibility" });
    expect(screen.getByText("Ablation checklist")).toHaveClass("coach-glow");

    await tool("point_to_lesion", { clock_start: 3, clock_end: 5, label: "Dense acetowhite" });
    expect(screen.getByText("Dense acetowhite: 3 to 5 o'clock")).toBeInTheDocument();

    await tool("show_teaching_card", { card: "ablation_eligibility" });
    expect(screen.getByRole("heading", { name: "Can I ablate?" })).toBeInTheDocument();

    await tool("ask_quiz", { question: "Can you ablate a TZ type 3?", options: ["Yes", "No"], correct_index: 1, explanation: "SCJ not visible." });
    fireEvent.click(screen.getByRole("button", { name: "B No" }));
    expect(await screen.findByText(/Correct\. SCJ not visible\./)).toBeInTheDocument();
    expect(sdk.sent).toContain("My answer is B: No");
    expect(screen.getByLabelText("Quiz score 1 of 1")).toBeInTheDocument();

    await tool("add_action_step", { step: "Refer for LEEP", why: "TZ type 3" });
    fireEvent.click(screen.getByRole("checkbox", { name: /Refer for LEEP/ }));
    await waitFor(() => expect(screen.getByRole("checkbox", { name: /Refer for LEEP/ })).toBeChecked());

    await tool("start_roleplay", { scenario: "Telling Grace her result" });
    expect(screen.getByText("Role-play · Kezia is the patient")).toBeInTheDocument();
    await tool("end_roleplay", { strengths: ["Calm tone"], improve: "Check she understood" });
    expect(screen.getByText("Calm tone")).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "Quiz me" }));
    expect(sdk.sent).toContain("Quiz me on this case.");
  });

  it("offers a practice lesson without a case", async () => {
    render(<CoachPanel variant="page" />);
    expect(await screen.findByText(/Practise reading VIA results/)).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Start lesson with Kezia" }));
    expect(await screen.findByRole("button", { name: "When can I ablate?" })).toBeInTheDocument();
    const start = fetchMock.mock.calls.find(([u]) => String(u) === "/api/v1/coach/sessions")!;
    expect(JSON.parse(String(start[1]!.body))).toEqual({});
  });
});

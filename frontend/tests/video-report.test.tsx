import { act, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { VideoReport } from "@/components/video-report";
import { mockFetch, videoReportFixture } from "./fixtures";

type Listener = (...args: unknown[]) => void;
const sdk = vi.hoisted(() => ({
  listeners: {} as Record<string, Listener>,
  spoken: [] as string[],
  options: undefined as unknown,
  stopped: false,
  reset() {
    this.listeners = {};
    this.spoken = [];
    this.options = undefined;
    this.stopped = false;
  },
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
  createClient: (_token: string, options: unknown) => {
    sdk.options = options;
    return {
      registerToolCallHandler: () => undefined,
      addListener: (event: string, fn: Listener) => {
        sdk.listeners[event] = fn;
      },
      streamToVideoElement: async () => {
        sdk.listeners.SESSION_READY?.("anam-session-9");
        sdk.listeners.VIDEO_PLAY_STARTED?.();
      },
      talk: async (text: string) => {
        sdk.spoken.push(text);
        // The avatar starts speaking, then finishes.
        sdk.listeners.MESSAGE_STREAM_EVENT_RECEIVED?.({ role: "persona", id: `m${sdk.spoken.length}`, content: text, endOfSpeech: false });
        sdk.listeners.MESSAGE_STREAM_EVENT_RECEIVED?.({ role: "persona", id: `m${sdk.spoken.length}`, content: "", endOfSpeech: true });
      },
      sendUserMessage: () => undefined,
      stopStreaming: async () => {
        sdk.stopped = true;
      },
      getInputAudioState: () => ({ isMuted: true }),
      muteInputAudio: () => undefined,
      unmuteInputAudio: () => undefined,
    };
  },
}));

beforeEach(() => sdk.reset());
afterEach(() => vi.unstubAllGlobals());

describe("VideoReport", () => {
  it("embeds the recording once the video is completed", async () => {
    mockFetch();
    render(<VideoReport interpretationId={7} pollMs={5} />);
    const frame = await screen.findByTitle("Video report");
    expect(frame.tagName).toBe("IFRAME");
    expect(frame).toHaveAttribute("src", "/player/viscan-7");
    expect(screen.getByRole("link", { name: "Open player" })).toHaveAttribute("href", "/player/viscan-7");
    expect(screen.getByRole("link", { name: "Download video" })).toHaveAttribute(
      "href",
      "https://videos.example/anam-vid-7.mp4",
    );
  });

  it("presents the confirmed report live while the recording is still rendering", async () => {
    const fetchMock = mockFetch({ video: [404, videoReportFixture("running")] });
    render(<VideoReport interpretationId={7} pollMs={5} idleCloseMs={20} />);

    // Nothing to present until the interpreter has created the report.
    const button = screen.getByRole("button", { name: "Preparing the report…" });
    expect(button).toBeDisabled();

    await screen.findByRole("button", { name: "Present now with the patient" });
    expect(screen.getByRole("status")).toHaveTextContent("Recording for the record");
    expect(screen.queryByTitle("Video report")).not.toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "Present now with the patient" }));

    await screen.findByText("Live · AI avatar");
    const sessionCall = fetchMock.mock.calls.find(([u]) => String(u) === "/api/v1/reports/viscan-7/session");
    expect(sessionCall?.[1]?.method).toBe("POST");
    // Presentation mode: microphone off so the avatar is not interrupted.
    expect(sdk.options).toEqual({ disableInputAudio: true });
    // The avatar speaks the confirmed script verbatim, paragraph by paragraph.
    await waitFor(() => expect(sdk.spoken).toHaveLength(3));
    expect(sdk.spoken[0]).toBe("Hello. This is your VIScan report.");
    expect(sdk.spoken[2]).toBe("Please attend the referral.");

    // A few seconds after it finished speaking the session is closed.
    await waitFor(() => expect(sdk.stopped).toBe(true));
    await screen.findByRole("button", { name: "Present again" });
  });

  it("can be stopped by the clinician", async () => {
    mockFetch({ video: [videoReportFixture("pending")] });
    render(<VideoReport interpretationId={7} pollMs={5} idleCloseMs={60_000} />);
    fireEvent.click(await screen.findByRole("button", { name: "Present now with the patient" }));
    await screen.findByText("Live · AI avatar");
    await act(async () => {
      fireEvent.click(screen.getByRole("button", { name: "Stop" }));
    });
    expect(sdk.stopped).toBe(true);
    expect(await screen.findByRole("button", { name: "Present again" })).toBeEnabled();
  });

  it("explains when the live session cannot start", async () => {
    mockFetch({ video: [videoReportFixture("pending")], sessionStatus: 502 });
    render(<VideoReport interpretationId={7} pollMs={5} />);
    fireEvent.click(await screen.findByRole("button", { name: "Present now with the patient" }));
    expect(await screen.findByText(/Request failed \(502\)|not reachable/)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Present now with the patient" })).toBeEnabled();
  });

  it("polls while the recording is being created and rendered", async () => {
    const fetchMock = mockFetch({ video: [404, videoReportFixture("pending"), videoReportFixture("running"), videoReportFixture()] });
    render(<VideoReport interpretationId={7} pollMs={5} />);
    expect(screen.getByRole("status")).toHaveTextContent("Preparing the video report");
    await screen.findByText(/Recording for the record/);
    await screen.findByTitle("Video report");
    const polls = fetchMock.mock.calls.filter(([u]) => String(u) === "/api/v1/reports/viscan-7/video");
    expect(polls.length).toBe(4);
  });

  it("explains when rendering failed", async () => {
    mockFetch({ video: [videoReportFixture("failed")] });
    render(<VideoReport interpretationId={7} pollMs={5} />);
    expect(await screen.findByText(/could not be generated/)).toBeInTheDocument();
    expect(screen.queryByTitle("Video report")).not.toBeInTheDocument();
  });

  it("degrades quietly when the avatar service is unreachable", async () => {
    mockFetch({ video: [502] });
    render(<VideoReport interpretationId={7} pollMs={5} />);
    expect(await screen.findByText(/not available right now/)).toBeInTheDocument();
  });

  it("renders nothing until the reading is confirmed", () => {
    const fetchMock = mockFetch();
    const { container } = render(<VideoReport interpretationId={7} enabled={false} />);
    expect(container).toBeEmptyDOMElement();
    expect(fetchMock).not.toHaveBeenCalled();
  });
});

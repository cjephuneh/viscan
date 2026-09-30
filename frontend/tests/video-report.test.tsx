import { render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { VideoReport } from "@/components/video-report";
import { mockFetch, videoReportFixture } from "./fixtures";

afterEach(() => vi.unstubAllGlobals());

describe("VideoReport", () => {
  it("embeds the player once the video is completed", async () => {
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

  it("polls while the report is being created and rendered", async () => {
    const fetchMock = mockFetch({ video: [404, videoReportFixture("pending"), videoReportFixture("running"), videoReportFixture()] });
    render(<VideoReport interpretationId={7} pollMs={5} />);
    expect(screen.getByRole("status")).toHaveTextContent("Preparing the video report");
    await screen.findByText(/Rendering the video/);
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

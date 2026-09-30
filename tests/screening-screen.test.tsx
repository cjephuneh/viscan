import { act, fireEvent, render, screen, within } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { ScreeningScreen } from "@/components/screening-screen";

function makeImageFile(
  name = "via-capture.png",
  type: string = "image/png",
  content = "fake-image-bytes",
) {
  return new File([content], name, { type });
}

function makeOversizedImageFile() {
  const file = new File(["tiny"], "huge.jpg", { type: "image/jpeg" });
  Object.defineProperty(file, "size", { value: 12 * 1024 * 1024 + 1 });
  return file;
}

function fileInput(container: HTMLElement) {
  const input = container.querySelector('input[type="file"]');
  if (!input) throw new Error("file input not found");
  return input as HTMLInputElement;
}

function uploadImage(container: HTMLElement, file: File = makeImageFile()) {
  fireEvent.change(fileInput(container), { target: { files: [file] } });
}

async function advanceToResult() {
  await act(async () => {
    vi.advanceTimersByTime(2000);
  });
}

function typeInto(element: HTMLElement, value: string) {
  fireEvent.change(element, { target: { value } });
}

describe("ScreeningScreen — VISCAN clinician dashboard", () => {
  beforeEach(() => {
    vi.useFakeTimers();
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it("shows the VISCAN brand and VIA cervical screening support on the first screen", () => {
    render(<ScreeningScreen />);

    expect(screen.getByRole("heading", { name: "VISCAN" })).toBeInTheDocument();
    expect(screen.getByText(/Supports VIA cervical screening/i)).toBeInTheDocument();
    expect(
      screen.getByText(/Place the screening image from the visit, review a reading/i),
    ).toBeInTheDocument();
  });

  it("does not display a calendar date or weekday date pill", () => {
    const { container } = render(<ScreeningScreen />);
    const text = container.textContent ?? "";

    expect(text).not.toMatch(
      /September|October|Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday/i,
    );
    expect(
      screen.queryByText(/\b\d{1,2}\s+(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)/i),
    ).not.toBeInTheDocument();
  });

  it("empty state explains the reading will appear and lists Suspicious and Not suspicious", () => {
    render(<ScreeningScreen />);

    expect(screen.getByText("The reading will appear here")).toBeInTheDocument();
    expect(screen.getByText(/Waiting for an image/i)).toBeInTheDocument();

    const possible = screen.getByRole("list", { name: "Possible readings" });
    expect(within(possible).getByText("Suspicious")).toBeInTheDocument();
    expect(within(possible).getByText("Not suspicious")).toBeInTheDocument();
  });

  it("accepts a JPG, PNG, or WEBP image, shows preview and file name, then a sample result", async () => {
    const { container } = render(<ScreeningScreen />);
    const file = makeImageFile("cervix-visit.webp", "image/webp");

    uploadImage(container, file);

    expect(screen.getByAltText("Screening image selected for this visit")).toHaveAttribute(
      "src",
      "blob:mock-screening-preview",
    );
    expect(screen.getByText("cervix-visit.webp")).toBeInTheDocument();
    expect(screen.getByText("Reading in progress")).toBeInTheDocument();
    expect(screen.getByText("Sample reading")).toBeInTheDocument();
    expect(screen.getAllByText("Preparing the reading").length).toBeGreaterThan(0);

    await advanceToResult();

    expect(screen.getByText("Awaiting your confirmation")).toBeInTheDocument();
    expect(screen.getByText("Sample reading · preview")).toBeInTheDocument();
    expect(screen.getByText("Suspicious", { selector: ".classification" })).toBeInTheDocument();
  });

  it("rejects a non-image file with a visible error", () => {
    const { container } = render(<ScreeningScreen />);
    const bad = makeImageFile("notes.txt", "text/plain", "not an image");

    uploadImage(container, bad);

    expect(screen.getByText("Use a JPG, PNG, or WEBP image.")).toBeInTheDocument();
    expect(screen.queryByAltText("Screening image selected for this visit")).not.toBeInTheDocument();
    expect(screen.getByText("The reading will appear here")).toBeInTheDocument();
  });

  it("rejects an image larger than 12 MB with a visible error", () => {
    const { container } = render(<ScreeningScreen />);

    uploadImage(container, makeOversizedImageFile());

    expect(
      screen.getByText("That image is larger than 12 MB. Choose a smaller one."),
    ).toBeInTheDocument();
    expect(screen.queryByAltText("Screening image selected for this visit")).not.toBeInTheDocument();
  });

  it("sample result shows preview label, findings, clinical notes, and confirm actions", async () => {
    const { container } = render(<ScreeningScreen />);
    uploadImage(container);
    await advanceToResult();

    expect(screen.getByText("Sample reading · preview")).toBeInTheDocument();
    expect(screen.getByText("Suspicious", { selector: ".classification" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Findings" })).toBeInTheDocument();
    expect(screen.getByText("Acetowhite change")).toBeInTheDocument();
    expect(screen.getByText("Clinical notes")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Confirm this finding" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Record the other finding" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Retake" })).toBeInTheDocument();
    expect(
      screen.getByText(/This screen is a preview|live interpreter is not connected/i),
    ).toBeInTheDocument();
  });

  it("lets the clinician switch the sample outcome between Suspicious and Not suspicious", async () => {
    const { container } = render(<ScreeningScreen />);
    uploadImage(container);
    await advanceToResult();

    expect(screen.getByText("Sample reading · preview")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Suspicious sample" })).toHaveClass("on");

    fireEvent.click(screen.getByRole("button", { name: "Not suspicious sample" }));

    expect(screen.getByText("Not suspicious", { selector: ".classification" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Not suspicious sample" })).toHaveClass("on");
    expect(
      screen.getByText(/does not flag a suspicious acetowhite change/i),
    ).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "Suspicious sample" }));

    expect(screen.getByRole("button", { name: "Suspicious sample" })).toHaveClass("on");
    expect(
      screen.getByText(/flags acetowhite change that should be reviewed/i),
    ).toBeInTheDocument();
  });

  it("confirm without a patient ID does not confirm and asks for a patient ID", async () => {
    const { container } = render(<ScreeningScreen />);
    uploadImage(container);
    await advanceToResult();

    fireEvent.click(screen.getByRole("button", { name: "Confirm this finding" }));

    expect(screen.getByText("Add the patient ID before confirming.")).toBeInTheDocument();
    expect(screen.getByText("Awaiting your confirmation")).toBeInTheDocument();
    expect(screen.queryByText("Confirmed by clinician")).not.toBeInTheDocument();
    expect(screen.queryByRole("heading", { name: "Digital record" })).not.toBeInTheDocument();
  });

  it("confirm with a patient ID shows a digital record and confirmed-by-clinician state", async () => {
    const { container } = render(<ScreeningScreen />);

    typeInto(screen.getByPlaceholderText("For example, PT-1042"), "PT-1042");
    uploadImage(container, makeImageFile("visit-image.png"));
    await advanceToResult();

    typeInto(
      screen.getByPlaceholderText("What you saw during the visit"),
      "Clear acetowhite area noted",
    );
    fireEvent.click(screen.getByRole("button", { name: "Confirm this finding" }));

    expect(screen.getByText("Confirmed by clinician")).toBeInTheDocument();
    expect(screen.getByText("Confirmed")).toBeInTheDocument();

    const record = screen.getByRole("heading", { name: "Digital record" }).closest("article");
    expect(record).not.toBeNull();
    const digitalRecord = within(record as HTMLElement);
    expect(digitalRecord.getByText("PT-1042")).toBeInTheDocument();
    expect(digitalRecord.getByText("visit-image.png")).toBeInTheDocument();
    expect(digitalRecord.getByText("Clear acetowhite area noted")).toBeInTheDocument();
    expect(digitalRecord.getByText("Suspicious")).toBeInTheDocument();
    expect(
      digitalRecord.getByText("Refer to a partner hospital if you agree with this reading."),
    ).toBeInTheDocument();
  });

  it("confirm with a patient ID and no notes shows None added in the digital record", async () => {
    const { container } = render(<ScreeningScreen />);

    typeInto(screen.getByPlaceholderText("For example, PT-1042"), "PT-2201");
    uploadImage(container);
    await advanceToResult();
    fireEvent.click(screen.getByRole("button", { name: "Confirm this finding" }));

    expect(screen.getByText("None added")).toBeInTheDocument();
    expect(screen.getByText("PT-2201")).toBeInTheDocument();
  });

  it("Remove or Retake clears the image and returns to the empty capture and reading state", async () => {
    const { container } = render(<ScreeningScreen />);

    uploadImage(container, makeImageFile("to-clear.png"));
    await advanceToResult();

    expect(screen.getByText("to-clear.png")).toBeInTheDocument();
    expect(screen.getByText("Sample reading · preview")).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "Retake" }));

    expect(screen.queryByAltText("Screening image selected for this visit")).not.toBeInTheDocument();
    expect(screen.queryByText("to-clear.png")).not.toBeInTheDocument();
    expect(screen.getByText("The reading will appear here")).toBeInTheDocument();
    expect(screen.getByText("Waiting for a capture")).toBeInTheDocument();
    expect(screen.getByText("Waiting for an image")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Choose image" })).toBeInTheDocument();

    uploadImage(container, makeImageFile("second.png"));
    expect(screen.getByText("second.png")).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "Remove" }));

    expect(screen.queryByText("second.png")).not.toBeInTheDocument();
    expect(screen.getByText("The reading will appear here")).toBeInTheDocument();
  });
});

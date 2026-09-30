import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { ScreeningScreen } from "@/components/screening-screen";
import { interpretationFixture, mockFetch } from "./fixtures";

function makeImageFile(name = "via-capture.png", type = "image/png") {
  return new File(["fake-image-bytes"], name, { type });
}

function fileInput(container: HTMLElement) {
  const input = container.querySelector('input[type="file"]');
  if (!input) throw new Error("file input not found");
  return input as HTMLInputElement;
}

function uploadImage(container: HTMLElement, file: File = makeImageFile()) {
  fireEvent.change(fileInput(container), { target: { files: [file] } });
}

const typeInto = (element: HTMLElement, value: string) => fireEvent.change(element, { target: { value } });

describe("ScreeningScreen", () => {
  let fetchMock: ReturnType<typeof mockFetch>;

  beforeEach(() => {
    fetchMock = mockFetch();
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("shows the brand and the visit fields", () => {
    render(<ScreeningScreen />);
    expect(screen.getByRole("heading", { name: "VISCAN" })).toBeInTheDocument();
    for (const label of ["Patient ID", "Age", "HIV status", "HPV test", "Pregnant", "Clinician ID"]) {
      expect(screen.getByLabelText(label)).toBeInTheDocument();
    }
    expect(screen.getByRole("group", { name: "Symptoms reported" })).toBeInTheDocument();
  });

  it("rejects unsupported and oversized files", () => {
    const { container } = render(<ScreeningScreen />);
    uploadImage(container, makeImageFile("scan.gif", "image/gif"));
    expect(screen.getByText("Use a JPG, PNG, or WEBP image.")).toBeInTheDocument();

    const huge = makeImageFile("huge.jpg", "image/jpeg");
    Object.defineProperty(huge, "size", { value: 11 * 1024 * 1024 });
    uploadImage(container, huge);
    expect(screen.getByText(/larger than 10 MB/)).toBeInTheDocument();
  });

  it("requires a patient ID before reading", () => {
    const { container } = render(<ScreeningScreen />);
    uploadImage(container);
    fireEvent.click(screen.getByRole("button", { name: "Read this image" }));
    expect(screen.getByText("Add the patient ID before reading the image.")).toBeInTheDocument();
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it("sends the image and visit details, then shows the suspicious reading", async () => {
    const { container } = render(<ScreeningScreen />);
    typeInto(screen.getByLabelText("Patient ID"), "PT-1");
    typeInto(screen.getByLabelText("Age"), "38");
    fireEvent.change(screen.getByLabelText("HIV status"), { target: { value: "positive" } });
    fireEvent.click(screen.getByLabelText("Bleeding after sex"));
    uploadImage(container);
    fireEvent.click(screen.getByRole("button", { name: "Read this image" }));

    expect(await screen.findByText("Suspicious", { selector: ".classification" })).toBeInTheDocument();
    const [url, init] = fetchMock.mock.calls[0];
    expect(url).toBe("/api/v1/interpret");
    const form = init!.body as FormData;
    expect(form.get("patient_external_id")).toBe("PT-1");
    expect(form.get("age")).toBe("38");
    expect(form.get("hiv_status")).toBe("positive");
    expect(form.getAll("symptoms")).toEqual(["postcoital_bleeding"]);
    expect(form.get("image")).toBeInstanceOf(File);

    expect(screen.getByText("Swede score")).toBeInTheDocument();
    expect(screen.getByText(/3–5 o'clock/)).toBeInTheDocument();
    expect(screen.getByRole("img", { name: /AI annotated/ })).toHaveAttribute(
      "src",
      "/api/v1/interpretations/7/overlay.png",
    );
  });

  it("shows the API error and lets the clinician retry", async () => {
    fetchMock.mockResolvedValueOnce(new Response(JSON.stringify({ error: "Model unavailable" }), { status: 502 }));
    const { container } = render(<ScreeningScreen />);
    typeInto(screen.getByLabelText("Patient ID"), "PT-1");
    uploadImage(container);
    fireEvent.click(screen.getByRole("button", { name: "Read this image" }));
    expect(await screen.findByText("Model unavailable")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Read this image" })).toBeInTheDocument();
  });

  it("requires a clinician ID, then confirms and links to referral and pharmacies", async () => {
    const { container } = render(<ScreeningScreen />);
    typeInto(screen.getByLabelText("Patient ID"), "PT-1");
    uploadImage(container);
    fireEvent.click(screen.getByRole("button", { name: "Read this image" }));
    await screen.findByRole("button", { name: "Confirm this finding" });

    fireEvent.click(screen.getByRole("button", { name: "Confirm this finding" }));
    expect(screen.getAllByText("Add your clinician ID before confirming.").length).toBeGreaterThan(0);

    typeInto(screen.getByLabelText("Clinician ID"), "nurse-07");
    fireEvent.click(screen.getByRole("button", { name: "Confirm this finding" }));

    const link = await screen.findByRole("link", { name: /Refer & find pharmacies/ });
    expect(link).toHaveAttribute("href", "/care/7");
    const annotate = fetchMock.mock.calls.find(([u]) => String(u).endsWith("/annotations"));
    expect(JSON.parse(annotate![1]!.body as string)).toMatchObject({
      clinician_id: "nurse-07",
      via_result: "VIA_POSITIVE",
    });
    expect(screen.getByText("Confirmed by clinician")).toBeInTheDocument();
    expect(await screen.findByRole("button", { name: "Send by SMS" })).toBeInTheDocument();
  });

  it("records the other finding and hides the referral link when not suspicious", async () => {
    const { container } = render(<ScreeningScreen />);
    typeInto(screen.getByLabelText("Patient ID"), "PT-1");
    typeInto(screen.getByLabelText("Clinician ID"), "nurse-07");
    uploadImage(container);
    fireEvent.click(screen.getByRole("button", { name: "Read this image" }));
    fireEvent.click(await screen.findByRole("button", { name: "Record the other finding" }));

    await screen.findByText("Confirmed by clinician");
    expect(screen.getByText("Not suspicious", { selector: ".classification" })).toBeInTheDocument();
    expect(screen.queryByRole("link", { name: /Refer & find pharmacies/ })).not.toBeInTheDocument();
  });

  it("sends the patient result by WhatsApp (demo)", async () => {
    const { container } = render(<ScreeningScreen />);
    typeInto(screen.getByLabelText("Patient ID"), "PT-1");
    typeInto(screen.getByLabelText("Clinician ID"), "nurse-07");
    uploadImage(container);
    fireEvent.click(screen.getByRole("button", { name: "Read this image" }));
    fireEvent.click(await screen.findByRole("button", { name: "Confirm this finding" }));

    fireEvent.click(await screen.findByRole("button", { name: "WhatsApp" }));
    await waitFor(() => expect(screen.getByLabelText("Message")).toHaveValue("WhatsApp preview"));
    typeInto(screen.getByLabelText("Patient phone"), "+250788000000");
    fireEvent.click(screen.getByRole("button", { name: "Send by WhatsApp" }));

    expect(await screen.findByText("simulated")).toBeInTheDocument();
    const call = fetchMock.mock.calls.find(([u]) => String(u).endsWith("/notifications"));
    expect(JSON.parse(call![1]!.body as string)).toMatchObject({
      channel: "whatsapp",
      phone: "+250788000000",
      sent_by: "nurse-07",
    });
  });

  it("shows the rationale, the recommended action and the patient explanation", async () => {
    const { container } = render(<ScreeningScreen />);
    typeInto(screen.getByLabelText("Patient ID"), "PT-1");
    uploadImage(container);
    fireEvent.click(screen.getByRole("button", { name: "Read this image" }));
    const { clinical_summary, recommendation } = interpretationFixture;
    expect(await screen.findByText(clinical_summary.rationale)).toBeInTheDocument();
    expect(screen.getByText(recommendation.action)).toBeInTheDocument();
    expect(screen.getByText(clinical_summary.patient_explanation)).toBeInTheDocument();
  });
});

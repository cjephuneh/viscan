import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { ScreeningScreen } from "@/components/screening-screen";
import { intakeFixture, interpretationFixture, mockFetch } from "./fixtures";

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

const interpretCall = (mock: ReturnType<typeof mockFetch>) =>
  mock.mock.calls.find(([u]) => String(u) === "/api/v1/interpret");

const typeInto = (element: HTMLElement, value: string) => fireEvent.change(element, { target: { value } });

describe("ScreeningScreen", () => {
  let fetchMock: ReturnType<typeof mockFetch>;

  beforeEach(() => {
    fetchMock = mockFetch();
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("shows the page title and the visit fields", () => {
    render(<ScreeningScreen />);
    expect(screen.getByRole("heading", { level: 1, name: "New screening" })).toBeInTheDocument();
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
    expect(interpretCall(fetchMock)).toBeUndefined();
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
    const [, init] = interpretCall(fetchMock)!;
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
    fetchMock = mockFetch({ interpretError: "Model unavailable" });
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

    // The avatar video report is requested after confirmation and embedded as an iframe.
    const frame = await screen.findByTitle("Video report");
    expect(frame.tagName).toBe("IFRAME");
    expect(frame).toHaveAttribute("src", "/player/viscan-7");
    const firstVideoPoll = fetchMock.mock.calls.findIndex(([u]) => String(u) === "/api/v1/reports/viscan-7/video");
    const annotateIndex = fetchMock.mock.calls.findIndex(([u]) => String(u).endsWith("/annotations"));
    expect(firstVideoPoll).toBeGreaterThan(annotateIndex);
  });

  it("sends an optional before-acetic-acid image and shows both frames", async () => {
    const { container } = render(<ScreeningScreen />);
    typeInto(screen.getByLabelText("Patient ID"), "PT-1");
    typeInto(screen.getByLabelText("Clinician ID"), "nurse-07");
    uploadImage(container);

    // Second (hidden) file input belongs to the optional baseline slot.
    const inputs = container.querySelectorAll('input[type="file"]');
    expect(inputs).toHaveLength(2);
    fireEvent.change(inputs[1], { target: { files: [makeImageFile("before.png")] } });
    expect(screen.getByText("before.png", { exact: false })).toBeInTheDocument();
    expect(screen.getByRole("img", { name: "Cervix before acetic acid" })).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "Read this image" }));
    await screen.findByRole("button", { name: "Confirm this finding" });

    const body = interpretCall(fetchMock)![1]!.body as FormData;
    expect((body.get("image") as File).name).toBe("via-capture.png");
    expect((body.get("image_before") as File).name).toBe("before.png");

    expect(screen.getByText("Before acetic acid (baseline)")).toBeInTheDocument();
    expect(screen.getByRole("img", { name: "AI annotated screening image with lesion markers" })).toBeInTheDocument();
  });

  it("does not send a before image when none was added", async () => {
    const { container } = render(<ScreeningScreen />);
    typeInto(screen.getByLabelText("Patient ID"), "PT-1");
    uploadImage(container);
    fireEvent.click(screen.getByRole("button", { name: "Read this image" }));
    await screen.findByRole("button", { name: "Confirm this finding" });
    const body = interpretCall(fetchMock)![1]!.body as FormData;
    expect(body.has("image_before")).toBe(false);
    expect(screen.queryByText("Before acetic acid (baseline)")).not.toBeInTheDocument();
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

  it("prefills the visit from a patient who checked in with Mia and links the reading", async () => {
    fetchMock = mockFetch({ waiting: [intakeFixture] });
    const { container } = render(<ScreeningScreen />);
    fireEvent.click(await screen.findByRole("button", { name: /Grace Uwase/ }));

    expect(screen.getByRole("heading", { name: /Grace Uwase, 38/ })).toBeInTheDocument();
    expect(screen.getByText("Reports postcoital bleeding.")).toBeInTheDocument();
    expect(screen.getByText(/Arrived very nervous \(5\/5\), now okay \(2\/5\)/)).toBeInTheDocument();
    expect(screen.getByLabelText("Patient ID")).toHaveValue("INT-K7M3Q");
    expect(screen.getByLabelText("Age")).toHaveValue(38);
    expect(screen.getByLabelText("HIV status")).toHaveValue("positive");
    expect(screen.getByLabelText("Bleeding after sex")).toBeChecked();

    typeInto(screen.getByLabelText("Clinician ID"), "nurse-07");
    uploadImage(container);
    fireEvent.click(screen.getByRole("button", { name: "Read this image" }));
    fireEvent.click(await screen.findByRole("button", { name: "Confirm this finding" }));
    const form = interpretCall(fetchMock)![1]!.body as FormData;
    expect(form.get("intake_id")).toBe("5");
    expect(await screen.findByLabelText("Patient phone")).toHaveValue("+250788111222");
    expect(screen.getByRole("button", { name: "Send by WhatsApp" })).toBeInTheDocument();
  });

  it("loads a check-in from the URL", async () => {
    render(<ScreeningScreen intakeId="5" />);
    expect(await screen.findByRole("heading", { name: /Grace Uwase/ })).toBeInTheDocument();
    expect(screen.getByLabelText("Patient ID")).toHaveValue("INT-K7M3Q");
  });

  it("opens Kezia, the clinical coach, next to the reading", async () => {
    const { container } = render(<ScreeningScreen />);
    typeInto(screen.getByLabelText("Patient ID"), "PT-1");
    uploadImage(container);
    fireEvent.click(screen.getByRole("button", { name: "Read this image" }));
    fireEvent.click(await screen.findByRole("button", { name: /Walk me through this with Kezia/ }));
    expect(screen.getByRole("complementary", { name: "Kezia, AI clinical coach" })).toBeInTheDocument();
    expect(container.querySelector('[data-coach="findings"]')).not.toBeNull();
    fireEvent.click(screen.getByRole("button", { name: "Close coach" }));
    expect(await screen.findByRole("button", { name: /Walk me through this with Kezia/ })).toBeInTheDocument();
  });
});

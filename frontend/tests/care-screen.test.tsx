import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { CareScreen } from "@/components/care-screen";
import { mockFetch } from "./fixtures";

vi.mock("next/dynamic", () => ({
  default: () =>
    function MapStub(props: { pharmacies: unknown[]; hospitals: unknown[] }) {
      return (
        <div data-testid="care-map">
          {props.pharmacies.length} pharmacies, {props.hospitals.length} hospitals
        </div>
      );
    },
}));

describe("CareScreen", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("shows the confirmed result, partner hospitals, pharmacies and supplies", async () => {
    mockFetch();
    render(<CareScreen interpretationId={7} />);

    expect(await screen.findByText("Patient PT-1 · Clinician-confirmed")).toBeInTheDocument();
    expect(await screen.findByText("Women's Health Centre (demo)")).toBeInTheDocument();
    expect(await screen.findByText("Pharmacie Conseil")).toBeInTheDocument();
    expect(screen.getByText("Sanitary pads")).toBeInTheDocument();
    expect(await screen.findByText("1 pharmacies, 1 hospitals")).toBeInTheDocument();
    expect(screen.getByText(/centred on the clinic's default location/)).toBeInTheDocument();

    const directions = screen.getAllByRole("link", { name: "Directions" });
    expect(directions[0].getAttribute("href")).toContain("google.com/maps/dir");
  });

  it("refers the patient to a partner hospital", async () => {
    const fetchMock = mockFetch();
    render(<CareScreen interpretationId={7} />);

    fireEvent.change(screen.getByLabelText("Referred by"), { target: { value: "nurse-07" } });
    fireEvent.click(await screen.findByRole("button", { name: "Refer to Women's Health Centre (demo)" }));

    expect(await screen.findByText("Referred ✓")).toBeInTheDocument();
    const call = fetchMock.mock.calls.find(([u]) => String(u).endsWith("/referrals"));
    expect(JSON.parse(call![1]!.body as string)).toEqual({ hospital_id: 11, referred_by: "nurse-07" });
    const made = screen.getByText("Referrals made").parentElement!;
    expect(within(made).getByText("Women's Health Centre (demo)")).toBeInTheDocument();
  });

  it("explains when the pharmacy search is unavailable", async () => {
    mockFetch({ pharmaciesStatus: 503 });
    render(<CareScreen interpretationId={7} />);
    expect(await screen.findByText("Pharmacy search is unavailable.")).toBeInTheDocument();
  });

  it("validates the phone number before sending results", async () => {
    mockFetch();
    render(<CareScreen interpretationId={7} />);
    await waitFor(() => expect(screen.getByLabelText("Message")).toHaveValue("SMS preview"));
    fireEvent.click(screen.getByRole("button", { name: "Send by SMS" }));
    expect(screen.getByText(/Enter the patient's phone number/)).toBeInTheDocument();
  });
});

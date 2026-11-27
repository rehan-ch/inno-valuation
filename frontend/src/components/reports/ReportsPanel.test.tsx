import { screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { errorResponse, fakeMe, fakeReport, fakeReports, stubApi } from "@/test/api";
import { renderWithMe } from "@/test/me";

import { ReportsPanel } from "./ReportsPanel";

vi.mock("next/navigation", async () => (await import("@/test/navigation")).navigationMock());

const ID = "55555555-5555-5555-5555-555555555555";
const PATH = `/api/v1/readiness/assessments/${ID}/reports`;
const REF = { kind: "readiness", assessmentId: ID } as const;
const OLD = "77777777-7777-7777-7777-777777777770";

let saved: string[] = [];

beforeEach(() => {
  saved = [];
  vi.stubGlobal("URL", Object.assign(URL, {
    createObjectURL: vi.fn(() => "blob:report"),
    revokeObjectURL: vi.fn(),
  }));
  // Record what would be saved instead of navigating.
  vi.spyOn(HTMLAnchorElement.prototype, "click").mockImplementation(function (this: HTMLAnchorElement) {
    saved.push(this.download);
  });
});

afterEach(() => {
  vi.useRealTimers();
});

function pdf(): Response {
  return new Response(new Uint8Array([0x25, 0x50, 0x44, 0x46]), {
    headers: { "Content-Type": "application/pdf" },
  });
}

describe("ReportsPanel", () => {
  it("makes a report, waits while it is drawn, then downloads it", async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true });
    let checks = 0;
    const calls = stubApi({
      [`GET ${PATH}`]: () => {
        checks += 1;
        // The first load finds none; the first check after asking finds it ready.
        return checks === 1
          ? fakeReports()
          : fakeReports({ reports: [fakeReport()] });
      },
      [`POST ${PATH}`]: fakeReports({
        reports: [fakeReport({ status: "queued", finished_at: null, file_size: null, page_count: null })],
      }),
      [`GET ${PATH}/${fakeReport().id}/file`]: () => pdf(),
    });
    const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime });
    renderWithMe(<ReportsPanel reportRef={REF} />, fakeMe());

    expect(await screen.findByText("No report has been made of this result yet.")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Make a PDF report" }));
    expect(await screen.findByText(/Preparing the PDF\. This takes a few seconds/)).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Make a PDF report" })).not.toBeInTheDocument();

    await vi.advanceTimersByTimeAsync(2100);
    const download = await screen.findByRole("button", { name: "Download PDF" });
    expect(screen.getByText(/Version 1 · .* · 5 pages · made by Olive Owner/)).toBeInTheDocument();
    expect(screen.getByRole("status", { hidden: true })).toHaveTextContent(
      "The PDF report is ready to download.",
    );

    await user.click(download);
    await vi.waitFor(() => expect(saved).toEqual(["innovaluation-readiness-report-v1.pdf"]));
    const file = calls.find((c) => c.path.endsWith("/file"));
    expect(file?.headers.get("Accept")).toBe("application/pdf");
    // A POST carries the CSRF header like every other write.
    expect(calls.find((c) => c.method === "POST")).toBeDefined();
  });

  it("lets someone who may not make one download the reports there are", async () => {
    stubApi({
      [`GET ${PATH}`]: fakeReports({ can_request: false, reports: [fakeReport()] }),
      [`GET ${PATH}/${fakeReport().id}/file`]: () => pdf(),
    });
    const user = userEvent.setup();
    renderWithMe(<ReportsPanel reportRef={REF} />, fakeMe());

    await user.click(await screen.findByRole("button", { name: "Download PDF" }));
    await vi.waitFor(() => expect(saved).toHaveLength(1));
    expect(screen.queryByRole("button", { name: /Make/ })).not.toBeInTheDocument();
  });

  it("tells someone who may not make one how a report gets made", async () => {
    stubApi({ [`GET ${PATH}`]: fakeReports({ can_request: false }) });
    renderWithMe(<ReportsPanel reportRef={REF} />, fakeMe());
    expect(
      await screen.findByText(/Someone who takes part in the assessment can make one/),
    ).toBeInTheDocument();
    expect(screen.queryByRole("button")).not.toBeInTheDocument();
  });

  it("offers to make a failed report again", async () => {
    stubApi({
      [`GET ${PATH}`]: fakeReports({
        reports: [fakeReport({ status: "failed", file_size: null, page_count: null })],
      }),
    });
    renderWithMe(<ReportsPanel reportRef={REF} />, fakeMe());
    expect(await screen.findByRole("alert")).toHaveTextContent("The PDF could not be made.");
    expect(screen.getByRole("button", { name: "Make it again" })).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Download PDF" })).not.toBeInTheDocument();
  });

  it("keeps earlier versions downloadable", async () => {
    stubApi({
      [`GET ${PATH}`]: fakeReports({
        reports: [
          fakeReport({ version: 2 }),
          fakeReport({ id: OLD, version: 1 }),
        ],
      }),
      [`GET ${PATH}/${OLD}/file`]: () => pdf(),
    });
    const user = userEvent.setup();
    renderWithMe(<ReportsPanel reportRef={REF} />, fakeMe());

    await user.click(await screen.findByText("Earlier versions (1)"));
    const earlier = within(screen.getByRole("list"));
    await user.click(earlier.getByRole("button", { name: "Download version 1" }));
    await vi.waitFor(() => expect(saved).toEqual(["innovaluation-readiness-report-v1.pdf"]));
    expect(screen.getByRole("button", { name: "Make a new version" })).toBeInTheDocument();
  });

  it("says why a download or a request was refused", async () => {
    stubApi({
      [`GET ${PATH}`]: fakeReports({ reports: [fakeReport()] }),
      [`GET ${PATH}/${fakeReport().id}/file`]: errorResponse(
        "report_file_missing",
        "This report's file is no longer available. Make it again.",
        410,
      ),
      [`POST ${PATH}`]: errorResponse(
        "too_many_requests",
        "Your organisation has made as many PDF reports as are allowed in one day.",
        429,
      ),
    });
    const user = userEvent.setup();
    renderWithMe(<ReportsPanel reportRef={REF} />, fakeMe());

    await user.click(await screen.findByRole("button", { name: "Download PDF" }));
    expect(await screen.findByText("This report's file is no longer available. Make it again.")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Make a new version" }));
    expect(
      await screen.findByText("Your organisation has made as many PDF reports as are allowed in one day."),
    ).toBeInTheDocument();
    expect(saved).toEqual([]);
  });

  it("stops checking after a failed check and offers to check again", async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true });
    let checks = 0;
    stubApi({
      [`GET ${PATH}`]: () => {
        checks += 1;
        if (checks === 1) {
          return fakeReports({ reports: [fakeReport({ status: "rendering", finished_at: null })] });
        }
        if (checks === 2) return errorResponse("network_error", "Offline.", 503);
        return fakeReports({ reports: [fakeReport()] });
      },
    });
    const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime });
    renderWithMe(<ReportsPanel reportRef={REF} />, fakeMe());

    expect(await screen.findByText(/Preparing the PDF\. This takes a few seconds/)).toBeInTheDocument();
    await vi.advanceTimersByTimeAsync(2100);
    await user.click(await screen.findByRole("button", { name: "Check again" }));
    await vi.advanceTimersByTimeAsync(2100);
    expect(await screen.findByRole("button", { name: "Download PDF" })).toBeInTheDocument();
  });

  it("asks for an idea's reports at the idea's address", async () => {
    const IDEA = "88888888-8888-8888-8888-888888888888";
    const calls = stubApi({
      [`GET /api/v1/ideas/${IDEA}/assessments/${ID}/reports`]: fakeReports({
        subject: "iq_assessment",
      }),
    });
    renderWithMe(
      <ReportsPanel reportRef={{ kind: "idea", ideaId: IDEA, assessmentId: ID }} />,
      fakeMe(),
    );
    expect(await screen.findByRole("button", { name: "Make a PDF report" })).toBeInTheDocument();
    expect(calls.map((c) => c.path)).toEqual([`/api/v1/ideas/${IDEA}/assessments/${ID}/reports`]);
  });
});

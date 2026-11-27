"use client";

import { useState } from "react";

import { Alert } from "@/components/ui/Alert";
import { Button } from "@/components/ui/Button";
import { Card, CardHeader } from "@/components/ui/Card";
import { Loading } from "@/components/ui/Loading";
import { ApiError } from "@/lib/api/client";
import { downloadReport, type ReportRef } from "@/lib/api/reports";
import type { ReportOut, ReportsOut } from "@/lib/api/types";
import { formatDateTime } from "@/lib/format";

import { isDrawing, useReports } from "./useReports";

/** Save a file the browser already holds, under `name`. */
function save(blob: Blob, name: string): void {
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = name;
  document.body.append(link);
  link.click();
  link.remove();
  window.setTimeout(() => URL.revokeObjectURL(url), 1000);
}

function fileName(reportRef: ReportRef, report: ReportOut): string {
  const kind = reportRef.kind === "readiness" ? "readiness" : "idea";
  return `innovaluation-${kind}-report-v${report.version}.pdf`;
}

function describe(report: ReportOut): string {
  const parts = [`Version ${report.version}`, formatDateTime(report.finished_at ?? report.created_at)];
  if (report.page_count) parts.push(report.page_count === 1 ? "1 page" : `${report.page_count} pages`);
  if (report.requested_by_name) parts.push(`made by ${report.requested_by_name}`);
  return parts.join(" · ");
}

/** The PDF reports of one result (Phase 7): make one, wait while it is drawn, download it
 * and its earlier versions. The PDF shows what this page shows, with the same numbers. */
export function ReportsPanel({ reportRef }: { reportRef: ReportRef }) {
  const { state, ask, asking, askError, stalled, arrived, checkAgain, target } =
    useReports(reportRef);
  const [downloading, setDownloading] = useState<string | null>(null);
  const [downloadError, setDownloadError] = useState<string | null>(null);

  async function download(report: ReportOut) {
    setDownloading(report.id);
    setDownloadError(null);
    try {
      save(await downloadReport(target, report.id), fileName(target, report));
    } catch (err) {
      setDownloadError(err instanceof ApiError ? err.message : "Could not download the report.");
    } finally {
      setDownloading(null);
    }
  }

  return (
    <Card>
      <CardHeader
        title="PDF report"
        description="A PDF of this result to keep or share, with the same numbers as this page. It is marked confidential to your organisation."
      />
      <p role="status" aria-live="polite" className="sr-only">
        {arrived ? "The PDF report is ready to download." : ""}
      </p>
      <div className="mt-4 space-y-3">
        {state.kind === "loading" && <Loading>Loading the reports...</Loading>}
        {state.kind === "error" && <Alert tone="error">{state.message}</Alert>}
        {state.kind === "ready" && (
          <ReportsBody
            reports={state.reports}
            onAsk={() => void ask()}
            asking={asking}
            stalled={stalled}
            onCheckAgain={checkAgain}
            onDownload={(report) => void download(report)}
            downloading={downloading}
          />
        )}
        {askError && <Alert tone="error">{askError}</Alert>}
        {downloadError && <Alert tone="error">{downloadError}</Alert>}
      </div>
    </Card>
  );
}

function ReportsBody({
  reports,
  onAsk,
  asking,
  stalled,
  onCheckAgain,
  onDownload,
  downloading,
}: {
  reports: ReportsOut;
  onAsk: () => void;
  asking: boolean;
  stalled: boolean;
  onCheckAgain: () => void;
  onDownload: (report: ReportOut) => void;
  downloading: string | null;
}) {
  const [newest, ...earlier] = reports.reports;
  const drawing = isDrawing(reports);
  const readyEarlier = earlier.filter((r) => r.status === "ready");

  return (
    <>
      {!newest && (
        <p className="text-sm text-neutral-600">
          {reports.can_request
            ? "No report has been made of this result yet."
            : "No report has been made of this result yet. Someone who takes part in the assessment can make one."}
        </p>
      )}

      {newest && drawing && (
        <div className="space-y-2">
          <p className="text-sm text-neutral-700">
            Preparing the PDF. This takes a few seconds; the person who asked is also emailed
            when it is ready.
          </p>
          {stalled ? (
            <Button variant="secondary" size="sm" onClick={onCheckAgain}>
              Check again
            </Button>
          ) : (
            <Loading>Preparing the PDF...</Loading>
          )}
        </div>
      )}

      {newest && newest.status === "ready" && (
        <div className="flex flex-wrap items-center justify-between gap-3 rounded-md border border-neutral-200 px-4 py-3">
          <p className="text-sm text-neutral-700">{describe(newest)}</p>
          <Button
            size="sm"
            busy={downloading === newest.id}
            onClick={() => onDownload(newest)}
          >
            Download PDF
          </Button>
        </div>
      )}

      {newest && newest.status === "failed" && (
        <Alert tone="error">The PDF could not be made. Make it again.</Alert>
      )}

      {reports.can_request && !drawing && (
        <div className="flex flex-wrap items-center gap-3">
          <Button
            variant={newest?.status === "ready" ? "secondary" : "primary"}
            size="sm"
            busy={asking}
            onClick={onAsk}
          >
            {!newest ? "Make a PDF report" : newest.status === "failed" ? "Make it again" : "Make a new version"}
          </Button>
          {newest?.status === "ready" && (
            <p className="text-xs text-neutral-500">
              A new version is made only when something on this page has changed, such as a
              target.
            </p>
          )}
        </div>
      )}

      {readyEarlier.length > 0 && (
        <details className="text-sm">
          <summary className="cursor-pointer text-neutral-700">
            Earlier versions ({readyEarlier.length})
          </summary>
          <ul className="mt-2 divide-y divide-neutral-100">
            {readyEarlier.map((report) => (
              <li key={report.id} className="flex flex-wrap items-center justify-between gap-2 py-2">
                <span className="text-neutral-600">{describe(report)}</span>
                <Button
                  variant="ghost"
                  size="sm"
                  busy={downloading === report.id}
                  onClick={() => onDownload(report)}
                  aria-label={`Download version ${report.version}`}
                >
                  Download
                </Button>
              </li>
            ))}
          </ul>
        </details>
      )}
    </>
  );
}

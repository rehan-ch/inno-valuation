// PDF reports of one result (Phase 7): a final readiness result, or an idea's confirmed
// scores. Making one returns at once with the newest report "queued"; poll listReports
// until it is ready or failed.
import { getBlob, getJson, postJson } from "./client";
import type { ReportsOut } from "./types";

/** Which result the reports are of. The two scores never share a report. */
export type ReportRef =
  | { kind: "readiness"; assessmentId: string }
  | { kind: "idea"; ideaId: string; assessmentId: string };

function path(ref: ReportRef): string {
  return ref.kind === "readiness"
    ? `/readiness/assessments/${ref.assessmentId}/reports`
    : `/ideas/${ref.ideaId}/assessments/${ref.assessmentId}/reports`;
}

export function listReports(ref: ReportRef): Promise<ReportsOut> {
  return getJson(path(ref));
}

/** Make a report. While one is on its way, or nothing has changed since the newest one,
 * the server returns that one instead of a new version. */
export function requestReport(ref: ReportRef): Promise<ReportsOut> {
  return postJson(path(ref));
}

export function downloadReport(ref: ReportRef, reportId: string): Promise<Blob> {
  return getBlob(`${path(ref)}/${reportId}/file`, "application/pdf");
}

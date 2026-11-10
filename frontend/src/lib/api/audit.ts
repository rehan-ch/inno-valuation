// /api/v1/audit: the organisation's activity log. Read-only.
import { apiUrl, getJson } from "./client";
import type { AuditFiltersOut, AuditPageOut } from "./types";

const BASE = "/audit";

export interface AuditFilter {
  action?: string;
  actorId?: string;
}

function query(filter: AuditFilter, before?: string | null): string {
  const params = new URLSearchParams();
  if (filter.action) params.set("action", filter.action);
  if (filter.actorId) params.set("actor_id", filter.actorId);
  if (before) params.set("before", before);
  const text = params.toString();
  return text ? `?${text}` : "";
}

export function listAuditEvents(filter: AuditFilter, before?: string | null): Promise<AuditPageOut> {
  return getJson(`${BASE}${query(filter, before)}`);
}

export function getAuditFilters(): Promise<AuditFiltersOut> {
  return getJson(`${BASE}/filters`);
}

/** The CSV download of the same list, with the same filters. */
export function auditExportUrl(filter: AuditFilter): string {
  return apiUrl(`${BASE}/export${query(filter)}`);
}

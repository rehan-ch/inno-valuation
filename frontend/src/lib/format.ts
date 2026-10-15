const DATE: Intl.DateTimeFormatOptions = { year: "numeric", month: "short", day: "numeric" };

export function formatDate(iso: string): string {
  return new Date(iso).toLocaleDateString(undefined, DATE);
}

export function formatDateTime(iso: string): string {
  return new Date(iso).toLocaleString(undefined, { ...DATE, hour: "2-digit", minute: "2-digit" });
}

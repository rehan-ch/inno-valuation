// Dates from the API are UTC-anchored instants whose calendar day is what matters
// (a grant ends at the end of its chosen day in UTC), so they are formatted in UTC.
// A local-time rendering would show the next day to anyone east of UTC.
const DATE: Intl.DateTimeFormatOptions = {
  year: "numeric",
  month: "short",
  day: "numeric",
  timeZone: "UTC",
};

export function formatDate(iso: string): string {
  return new Date(iso).toLocaleDateString(undefined, DATE);
}

export function formatDateTime(iso: string): string {
  return new Date(iso).toLocaleString(undefined, { ...DATE, hour: "2-digit", minute: "2-digit" });
}

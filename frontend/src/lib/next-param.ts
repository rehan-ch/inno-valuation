/** The same-site path a ?next= parameter may send the visitor to after signing in, or
 * null when it would leave the site.
 *
 * The raw value must start with a single "/" and resolve to this site's origin. Only the
 * resolved path and query are returned, never the raw string: URL parsers drop tabs and
 * newlines and treat backslashes as slashes, so "/\t/evil.com" or "/\evil.com" would
 * otherwise reach the router as a link to another host. */
export function safeNextPath(raw: string | null, origin: string): string | null {
  if (!raw || !raw.startsWith("/") || raw.startsWith("//")) return null;
  let url: URL;
  try {
    url = new URL(raw, origin);
  } catch {
    return null;
  }
  if (url.origin !== origin) return null;
  return url.pathname + url.search;
}

/** The ?next= value of the current page, checked with safeNextPath. */
export function safeNextFromLocation(): string | null {
  const raw = new URLSearchParams(window.location.search).get("next");
  return safeNextPath(raw, window.location.origin);
}

/** The sign-in link that brings the visitor back to where they are, hash included
 * (an invitation token travels in the hash and never reaches the server). */
export function signInHref(): string {
  const next = window.location.pathname + window.location.search;
  return `/sign-in?next=${encodeURIComponent(next)}${window.location.hash}`;
}

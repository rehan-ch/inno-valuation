// Email links carry their single-use token in the URL fragment (#token=...), which
// browsers never send to a server, so it stays out of logs and Referer headers.

export function readHashToken(): string | null {
  const hash = window.location.hash.replace(/^#/, "");
  return hash ? new URLSearchParams(hash).get("token") : null;
}

export function clearHash(): void {
  window.history.replaceState(null, "", window.location.pathname + window.location.search);
}

"use client";

import { useId, useState } from "react";

import { useMe } from "@/components/app/me-context";
import { ApiError } from "@/lib/api/client";
import { setActiveOrganisation } from "@/lib/api/me";

/** Switches the active organisation: memberships first, then consulting access. */
export function OrgSwitcher() {
  const { me, update } = useMe();
  const id = useId();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const options = [...me.memberships, ...me.consultant_organisations];
  if (options.length === 0) return null;

  async function choose(organisationId: string) {
    if (!organisationId || organisationId === me.active_organisation_id) return;
    setBusy(true);
    setError(null);
    try {
      update(await setActiveOrganisation(organisationId));
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Something went wrong.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="min-w-0">
      <label htmlFor={id} className="sr-only">
        Organisation
      </label>
      <select
        id={id}
        value={me.active_organisation_id ?? ""}
        onChange={(event) => void choose(event.target.value)}
        disabled={busy}
        className="block h-8 w-full min-w-0 max-w-56 truncate rounded-md border border-neutral-300 bg-white pr-7 pl-2.5 text-[13px] font-medium text-neutral-900 shadow-xs focus:outline-2 focus:-outline-offset-1 focus:outline-primary disabled:text-neutral-500"
      >
        {me.active_organisation_id === null && <option value="">Choose organisation</option>}
        <optgroup label="Your organisations">
          {me.memberships.map((m) => (
            <option key={m.organisation_id} value={m.organisation_id}>
              {m.organisation_name}
            </option>
          ))}
        </optgroup>
        {me.consultant_organisations.length > 0 && (
          <optgroup label="Consulting access">
            {me.consultant_organisations.map((o) => (
              <option key={o.organisation_id} value={o.organisation_id}>
                {o.organisation_name}
              </option>
            ))}
          </optgroup>
        )}
      </select>
      {error && (
        <p role="alert" className="mt-1 text-xs text-red-700">
          {error}
        </p>
      )}
    </div>
  );
}

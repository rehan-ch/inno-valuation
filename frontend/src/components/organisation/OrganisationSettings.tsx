"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import type { FormEvent } from "react";

import { useMe } from "@/components/app/me-context";
import { Alert } from "@/components/ui/Alert";
import { Button } from "@/components/ui/Button";
import { Card, CardTitle, PageHeader } from "@/components/ui/Card";
import { TextField } from "@/components/ui/fields";
import { Loading } from "@/components/ui/Loading";
import { ApiError } from "@/lib/api/client";
import { getOrganisation, updateOrganisation } from "@/lib/api/organisation";
import type { OrganisationOut } from "@/lib/api/types";
import { useSubmit } from "@/lib/forms";
import { canManage } from "@/lib/roles";

type State =
  | { kind: "loading" }
  | { kind: "error"; message: string }
  | { kind: "ready"; org: OrganisationOut };

/** The organisation profile: name, business details and the currency (P2.03). */
export function OrganisationSettings() {
  const { me } = useMe();
  const activeOrgId = me.active_organisation_id;
  const [state, setState] = useState<State>({ kind: "loading" });

  useEffect(() => {
    if (!activeOrgId) return;
    let cancelled = false;
    getOrganisation()
      .then((org) => {
        if (!cancelled) setState({ kind: "ready", org });
      })
      .catch((err: unknown) => {
        if (!cancelled) {
          setState({
            kind: "error",
            message: err instanceof ApiError ? err.message : "Something went wrong.",
          });
        }
      });
    return () => {
      cancelled = true;
    };
  }, [activeOrgId]);

  if (!activeOrgId) {
    return (
      <div className="space-y-4">
        <PageHeader title="Organisation settings" />
        <Alert tone="info">
          Choose an organisation in the switcher above, or{" "}
          <Link href="/organisations/new" className="underline">
            create one
          </Link>
          .
        </Alert>
      </div>
    );
  }

  if (state.kind === "loading") return <Loading>Loading the organisation...</Loading>;
  if (state.kind === "error") return <Alert tone="error">{state.message}</Alert>;

  const { org } = state;

  if (!canManage(org.role)) {
    return (
      <div className="space-y-4">
        <PageHeader title="Organisation settings" description={org.name} />
        <Alert tone="info">Only an owner or admin can edit the organisation profile.</Alert>
      </div>
    );
  }

  if (org.status !== "active") {
    return (
      <div className="space-y-4">
        <PageHeader title="Organisation settings" description={org.name} />
        <Alert tone="info">This organisation is archived, so its profile is view-only.</Alert>
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-xl space-y-6">
      <PageHeader
        title="Organisation settings"
        description="The profile and currency of the active organisation."
      />
      <SettingsForm
        org={org}
        onSaved={(saved) =>
          setState((prev) => (prev.kind === "ready" ? { ...prev, org: saved } : prev))
        }
      />
    </div>
  );
}

function SettingsForm({
  org,
  onSaved,
}: {
  org: OrganisationOut;
  onSaved: (org: OrganisationOut) => void;
}) {
  const { refresh } = useMe();
  const { busy, error, run } = useSubmit();
  const [name, setName] = useState(org.name);
  const [description, setDescription] = useState(org.description ?? "");
  const [industry, setIndustry] = useState(org.industry ?? "");
  const [country, setCountry] = useState(org.country ?? "");
  const [sizeBand, setSizeBand] = useState(org.size_band ?? "");
  const [revenueBand, setRevenueBand] = useState(org.revenue_band ?? "");
  const [founderNames, setFounderNames] = useState(org.founder_names ?? "");
  const [website, setWebsite] = useState(org.website ?? "");
  const [contactName, setContactName] = useState(org.primary_contact_name ?? "");
  const [contactEmail, setContactEmail] = useState(org.primary_contact_email ?? "");
  const [currency, setCurrency] = useState(org.currency);
  const [nameError, setNameError] = useState<string | undefined>(undefined);
  const [currencyError, setCurrencyError] = useState<string | undefined>(undefined);
  const [saved, setSaved] = useState(false);

  async function handleSubmit(event: FormEvent) {
    event.preventDefault();
    setSaved(false);
    const invalidName = name.trim() ? undefined : "Enter the organisation's name.";
    const invalidCurrency = /^[A-Za-z]{3}$/.test(currency)
      ? undefined
      : "Use a 3-letter code, like USD.";
    if (invalidName || invalidCurrency) {
      setNameError(invalidName);
      setCurrencyError(invalidCurrency);
      return;
    }
    const result = await run(() =>
      updateOrganisation({
        name,
        description: description || null,
        industry: industry || null,
        country: country ? country.toUpperCase() : null,
        size_band: sizeBand || null,
        revenue_band: revenueBand || null,
        founder_names: founderNames || null,
        website: website || null,
        primary_contact_name: contactName || null,
        primary_contact_email: contactEmail || null,
        currency: currency.toUpperCase(),
      }),
    );
    if (result) {
      onSaved(result);
      setSaved(true);
      await refresh(); // the switcher shows the organisation's name
    }
  }

  return (
    <Card>
      <CardTitle>Profile</CardTitle>
      <form onSubmit={(e) => void handleSubmit(e)} className="mt-4 space-y-4" noValidate>
        {error && <Alert tone="error">{error.message}</Alert>}
        {saved && <Alert tone="success">Saved.</Alert>}
        <TextField
          label="Name"
          name="name"
          required
          error={nameError}
          value={name}
          onChange={(e) => {
            setName(e.target.value);
            setNameError(undefined);
          }}
        />
        <TextField
          label="Description"
          name="description"
          value={description}
          onChange={(e) => setDescription(e.target.value)}
        />
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
          <TextField
            label="Industry"
            name="industry"
            value={industry}
            onChange={(e) => setIndustry(e.target.value)}
          />
          <TextField
            label="Country"
            name="country"
            maxLength={2}
            hint="2-letter code, e.g. US."
            value={country}
            onChange={(e) => setCountry(e.target.value)}
          />
          <TextField
            label="Company size"
            name="size_band"
            hint="e.g. 11 to 50 people."
            value={sizeBand}
            onChange={(e) => setSizeBand(e.target.value)}
          />
          <TextField
            label="Revenue band"
            name="revenue_band"
            hint="e.g. 1M to 10M."
            value={revenueBand}
            onChange={(e) => setRevenueBand(e.target.value)}
          />
        </div>
        <TextField
          label="Founders"
          name="founder_names"
          value={founderNames}
          onChange={(e) => setFounderNames(e.target.value)}
        />
        <TextField
          label="Website"
          type="url"
          name="website"
          hint="Full address, e.g. https://example.com."
          value={website}
          onChange={(e) => setWebsite(e.target.value)}
        />
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
          <TextField
            label="Primary contact name"
            name="primary_contact_name"
            value={contactName}
            onChange={(e) => setContactName(e.target.value)}
          />
          <TextField
            label="Primary contact email"
            type="email"
            name="primary_contact_email"
            value={contactEmail}
            onChange={(e) => setContactEmail(e.target.value)}
          />
        </div>
        <div className="sm:w-48">
          <TextField
            label="Currency"
            name="currency"
            maxLength={3}
            hint="3-letter code, e.g. USD."
            required
            error={currencyError}
            value={currency}
            onChange={(e) => {
              setCurrency(e.target.value);
              setCurrencyError(undefined);
            }}
          />
        </div>
        <Button type="submit" busy={busy}>
          Save changes
        </Button>
      </form>
    </Card>
  );
}

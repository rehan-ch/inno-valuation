"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";
import type { FormEvent } from "react";

import { useMe } from "@/components/app/me-context";
import { Alert } from "@/components/ui/Alert";
import { Button } from "@/components/ui/Button";
import { Card, PageHeader } from "@/components/ui/Card";
import { TextField } from "@/components/ui/fields";
import { createOrganisation } from "@/lib/api/organisation";
import { useSubmit } from "@/lib/forms";

export function NewOrganisationForm() {
  const { refresh } = useMe();
  const router = useRouter();
  const { busy, error, run } = useSubmit();
  const [name, setName] = useState("");
  const [industry, setIndustry] = useState("");
  const [country, setCountry] = useState("");
  const [sizeBand, setSizeBand] = useState("");
  const [currency, setCurrency] = useState("USD");
  const [website, setWebsite] = useState("");
  const [description, setDescription] = useState("");
  const [nameError, setNameError] = useState<string | undefined>(undefined);
  const [currencyError, setCurrencyError] = useState<string | undefined>(undefined);

  async function handleSubmit(event: FormEvent) {
    event.preventDefault();
    const invalidName = name.trim() ? undefined : "Enter the organisation's name.";
    const invalidCurrency = /^[A-Za-z]{3}$/.test(currency)
      ? undefined
      : "Use a 3-letter code, like USD.";
    if (invalidName || invalidCurrency) {
      setNameError(invalidName);
      setCurrencyError(invalidCurrency);
      return;
    }
    const org = await run(() =>
      createOrganisation({
        name,
        industry: industry || null,
        country: country ? country.toUpperCase() : null,
        size_band: sizeBand || null,
        currency: currency.toUpperCase() || "USD",
        website: website || null,
        description: description || null,
      }),
    );
    if (org) {
      // The new organisation became the active one in the session; re-read /me, then go.
      await refresh();
      router.push("/dashboard");
    }
  }

  return (
    <div className="mx-auto max-w-xl space-y-6">
      <PageHeader
        title="Create an organisation"
        description="You become its owner and can invite your team."
      />
      <Card>
        <form onSubmit={(e) => void handleSubmit(e)} className="space-y-4" noValidate>
          {error && <Alert tone="error">{error.message}</Alert>}
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
            label="Industry"
            name="industry"
            value={industry}
            onChange={(e) => setIndustry(e.target.value)}
          />
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
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
          <TextField
            label="Website"
            type="url"
            name="website"
            value={website}
            onChange={(e) => setWebsite(e.target.value)}
          />
          <TextField
            label="Description"
            name="description"
            value={description}
            onChange={(e) => setDescription(e.target.value)}
          />
          <Button type="submit" busy={busy}>
            Create organisation
          </Button>
        </form>
      </Card>
    </div>
  );
}

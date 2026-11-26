
"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";
import type { FormEvent, ReactNode } from "react";
import {
  ArrowLeft,
  ArrowRight,
  BadgeCheck,
  Building2,
  CheckCircle2,
  CircleDollarSign,
  Globe2,
  Layers3,
  Plus,
  Rocket,
  ShieldCheck,
  Sparkles,
  UsersRound,
} from "lucide-react";

import { useMe } from "@/components/app/me-context";
import { Alert } from "@/components/ui/Alert";
import { Button } from "@/components/ui/Button";
import { CurrencySelect } from "@/components/ui/CurrencySelect";
import { TextField } from "@/components/ui/fields";
import { createOrganisation } from "@/lib/api/organisation";
import { useSubmit } from "@/lib/forms";

function Field({
  children,
  wide = false,
}: {
  children: ReactNode;
  wide?: boolean;
}) {
  return (
    <div className={`iv-os-field ${wide ? "iv-os-field-wide" : ""}`}>
      {children}
    </div>
  );
}

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
  const [nameError, setNameError] = useState<string | undefined>();

  const fieldsCompleted = [
    name.trim(),
    industry.trim(),
    country.trim(),
    sizeBand.trim(),
    website.trim(),
    description.trim(),
  ].filter(Boolean).length;

  async function handleSubmit(event: FormEvent) {
    event.preventDefault();

    if (!name.trim()) {
      setNameError("Enter the organisation's name.");
      return;
    }

    const org = await run(() =>
      createOrganisation({
        name,
        industry: industry || null,
        country: country ? country.toUpperCase() : null,
        size_band: sizeBand || null,
        currency,
        website: website || null,
        description: description || null,
      }),
    );

    if (org) {
      await refresh();
      router.push("/dashboard");
    }
  }

  return (
    <div className="iv-os-page iv-os-create-page">
      <div className="iv-os-topline">
        <Link href="/dashboard" className="iv-os-back">
          <ArrowLeft size={16} aria-hidden="true" />
          Back to dashboard
        </Link>
        <span className="iv-os-topline-tag">
          <Sparkles size={14} aria-hidden="true" />
          New workspace
        </span>
      </div>

      <div className="iv-os-page-heading">
        <div>
          <div className="iv-os-eyebrow">
            <span className="iv-os-gold-dot" />
            WORKSPACE ONBOARDING
          </div>
          <h1>
            Create your <span>organisation.</span>
          </h1>
          <p>
            Build a dedicated workspace for your organisation,
            your people and your innovation journey.
          </p>
        </div>

        <div className="iv-os-heading-icon" aria-hidden="true">
          <Plus size={30} strokeWidth={1.5} />
        </div>
      </div>

      <div className="iv-os-layout">
        <div className="iv-os-content">
          <form
            onSubmit={(event) => void handleSubmit(event)}
            noValidate
            className="iv-os-form"
          >
            {error && <Alert tone="error">{error.message}</Alert>}

            <section className="iv-os-panel">
              <div className="iv-os-section-head">
                <div className="iv-os-section-icon" aria-hidden="true">
                  <Building2 size={22} />
                </div>
                <div className="iv-os-section-copy">
                  <span className="iv-os-section-eyebrow">
                    01 / THE BASICS
                  </span>
                  <h2>Organisation details</h2>
                  <p>
                    Tell us a little about the organisation
                    you&apos;re creating.
                  </p>
                </div>
              </div>

              <div className="iv-os-fields">
                <Field wide>
                  <TextField
                    label="Name"
                    name="name"
                    required
                    error={nameError}
                    value={name}
                    onChange={(event) => {
                      setName(event.target.value);
                      setNameError(undefined);
                    }}
                  />
                </Field>

                <Field wide>
                  <TextField
                    label="Description"
                    name="description"
                    value={description}
                    onChange={(event) =>
                      setDescription(event.target.value)
                    }
                  />
                </Field>

                <Field wide>
                  <TextField
                    label="Industry"
                    name="industry"
                    value={industry}
                    onChange={(event) =>
                      setIndustry(event.target.value)
                    }
                  />
                </Field>

                <Field>
                  <TextField
                    label="Country"
                    name="country"
                    maxLength={2}
                    hint="2-letter code, e.g. US."
                    value={country}
                    onChange={(event) =>
                      setCountry(event.target.value)
                    }
                  />
                </Field>

                <Field>
                  <TextField
                    label="Company size"
                    name="size_band"
                    hint="e.g. 11 to 50 people."
                    value={sizeBand}
                    onChange={(event) =>
                      setSizeBand(event.target.value)
                    }
                  />
                </Field>
              </div>
            </section>

            <section className="iv-os-panel">
              <div className="iv-os-section-head">
                <div className="iv-os-section-icon" aria-hidden="true">
                  <Globe2 size={22} />
                </div>
                <div className="iv-os-section-copy">
                  <span className="iv-os-section-eyebrow">
                    02 / ONLINE IDENTITY
                  </span>
                  <h2>Digital presence</h2>
                  <p>
                    Add your organisation&apos;s website
                    if you have one.
                  </p>
                </div>
              </div>

              <div className="iv-os-fields">
                <Field wide>
                  <TextField
                    label="Website"
                    type="url"
                    name="website"
                    value={website}
                    onChange={(event) =>
                      setWebsite(event.target.value)
                    }
                  />
                </Field>
              </div>
            </section>

            <section className="iv-os-panel">
              <div className="iv-os-section-head">
                <div className="iv-os-section-icon" aria-hidden="true">
                  <CircleDollarSign size={22} />
                </div>
                <div className="iv-os-section-copy">
                  <span className="iv-os-section-eyebrow">
                    03 / WORKSPACE PREFERENCES
                  </span>
                  <h2>Reporting currency</h2>
                  <p>
                    Set the preferred currency for financial
                    information in your workspace.
                  </p>
                </div>
              </div>

              <div className="iv-os-fields">
                <Field wide>
                  <div className="iv-os-currency">
                    <CurrencySelect
                      value={currency}
                      onChange={setCurrency}
                      hint="Investments and Value for Money are shown in this currency."
                    />
                  </div>
                </Field>
              </div>
            </section>

            <div className="iv-os-save-panel">
              <div className="iv-os-save-copy">
                <span className="iv-os-save-icon">
                  <ShieldCheck size={21} aria-hidden="true" />
                </span>
                <div>
                  <strong>Ready to create?</strong>
                  <p>
                    You&apos;ll become the owner of this organisation.
                  </p>
                </div>
              </div>

              <Button type="submit" busy={busy}>
                <span className="iv-os-button-content">
                  <Plus size={17} aria-hidden="true" />
                  Create organisation
                  <ArrowRight size={17} aria-hidden="true" />
                </span>
              </Button>
            </div>

            <div className="iv-os-bottom-caption">
              <Layers3 size={15} aria-hidden="true" />
              You can update optional details after creation.
            </div>
          </form>
        </div>

        <aside className="iv-os-sidebar">
          <div className="iv-os-sidebar-inner">
            <div className="iv-os-identity-card iv-os-create-identity">
              <div className="iv-os-identity-decoration" />

              <div className="iv-os-identity-top">
                <div className="iv-os-identity-icon">
                  <Rocket size={24} aria-hidden="true" />
                </div>
                <Sparkles size={20} className="iv-os-gold-icon" />
              </div>

              <span className="iv-os-identity-label">
                YOUR NEXT CHAPTER
              </span>

              <h2>
                {name.trim() || "A new beginning."}
              </h2>

              <p>
                A dedicated space to explore, assess and
                strengthen your innovation capabilities.
              </p>

              <div className="iv-os-identity-divider" />

              <div className="iv-os-identity-detail">
                <span>Your role</span>
                <strong>Owner</strong>
              </div>
              <div className="iv-os-identity-detail">
                <span>Currency</span>
                <strong>{currency}</strong>
              </div>
              <div className="iv-os-identity-detail">
                <span>Workspace</span>
                <strong>New</strong>
              </div>
            </div>

            <div className="iv-os-help-card">
              <span className="iv-os-help-icon">
                <BadgeCheck size={20} aria-hidden="true" />
              </span>

              <h3>Profile progress</h3>

              <p>
                Start with the organisation name. You can fill
                in the remaining details now or later.
              </p>

              <div className="iv-os-create-progress">
                <div className="iv-os-create-progress-top">
                  <span>Optional profile setup</span>
                  <strong>{fieldsCompleted} / 6</strong>
                </div>
                <div
                  className="iv-os-create-progress-track"
                  role="progressbar"
                  aria-valuemin={0}
                  aria-valuemax={6}
                  aria-valuenow={fieldsCompleted}
                  aria-label="Profile fields completed"
                >
                  <span
                    style={{
                      width: `${(fieldsCompleted / 6) * 100}%`,
                    }}
                  />
                </div>
              </div>

              <div className="iv-os-help-divider" />

              <div className="iv-os-help-point">
                <CheckCircle2 size={16} />
                Create your organisation
              </div>
              <div className="iv-os-help-point">
                <UsersRound size={16} />
                Invite your team afterwards
              </div>
              <div className="iv-os-help-point">
                <Sparkles size={16} />
                Begin your readiness journey
              </div>
            </div>
          </div>
        </aside>
      </div>
    </div>
  );
}

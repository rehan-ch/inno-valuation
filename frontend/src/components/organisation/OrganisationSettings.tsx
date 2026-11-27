
"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import type { FormEvent, ReactNode } from "react";
import {
  ArrowLeft,
  ArrowUpRight,
  BadgeCheck,
  Building2,
  CheckCircle2,
  ChevronRight,
  CircleDollarSign,
  ContactRound,
  Globe2,
  Info,
  Layers3,
  LockKeyhole,
  Save,
  ShieldCheck,
  Sparkles,
  UsersRound,
  History,
  SlidersHorizontal,
} from "lucide-react";

import { useMe } from "@/components/app/me-context";
import { Alert } from "@/components/ui/Alert";
import { Button } from "@/components/ui/Button";
import { CurrencySelect } from "@/components/ui/CurrencySelect";
import { TextField } from "@/components/ui/fields";
import { Loading } from "@/components/ui/Loading";
import { ApiError } from "@/lib/api/client";
import {
  getOrganisation,
  updateOrganisation,
} from "@/lib/api/organisation";
import type { OrganisationOut } from "@/lib/api/types";
import { useSubmit } from "@/lib/forms";
import { canManage } from "@/lib/roles";

type State =
  | { kind: "loading" }
  | { kind: "error"; message: string }
  | { kind: "ready"; org: OrganisationOut };

function SectionHeading({
  icon,
  eyebrow,
  title,
  description,
}: {
  icon: ReactNode;
  eyebrow: string;
  title: string;
  description: string;
}) {
  return (
    <div className="iv-os-section-head">
      <div className="iv-os-section-icon" aria-hidden="true">
        {icon}
      </div>
      <div className="iv-os-section-copy">
        <span className="iv-os-section-eyebrow">
          {eyebrow}
        </span>
        <h2>{title}</h2>
        <p>{description}</p>
      </div>
    </div>
  );
}

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

export function OrganisationSettings() {
  const { me } = useMe();
  const activeOrgId = me.active_organisation_id;
  const [state, setState] = useState<State>({
    kind: "loading",
  });

  useEffect(() => {
    if (!activeOrgId) return;

    let cancelled = false;

    async function load() {
      setState({ kind: "loading" });

      try {
        const org = await getOrganisation();

        if (!cancelled) {
          setState({ kind: "ready", org });
        }
      } catch (err: unknown) {
        if (!cancelled) {
          setState({
            kind: "error",
            message:
              err instanceof ApiError
                ? err.message
                : "Something went wrong.",
          });
        }
      }
    }

    void load();

    return () => {
      cancelled = true;
    };
  }, [activeOrgId]);

  if (!activeOrgId) {
    return (
      <div className="iv-os-page">
        <div className="iv-os-empty">
          <Building2 size={36} aria-hidden="true" />
          <h1>Organisation settings</h1>
          <Alert tone="info">
            Choose an organisation in the switcher above, or{" "}
            <Link href="/organisations/new" className="underline">
              create one
            </Link>
            .
          </Alert>
        </div>
      </div>
    );
  }

  if (
    state.kind === "loading" ||
    (state.kind === "ready" &&
      state.org.id !== activeOrgId)
  ) {
    return (
      <div className="iv-os-page">
        <Loading>Loading the organisation...</Loading>
      </div>
    );
  }

  if (state.kind === "error") {
    return (
      <div className="iv-os-page">
        <Alert tone="error">{state.message}</Alert>
      </div>
    );
  }

  const { org } = state;

  if (!canManage(org.role)) {
    return (
      <div className="iv-os-page">
        <div className="iv-os-empty">
          <LockKeyhole size={36} aria-hidden="true" />
          <h1>Organisation settings</h1>
          <p>{org.name}</p>
          <Alert tone="info">
            Only an owner or admin can edit the organisation profile.
          </Alert>
        </div>
      </div>
    );
  }

  if (org.status !== "active") {
    return (
      <div className="iv-os-page">
        <div className="iv-os-empty">
          <LockKeyhole size={36} aria-hidden="true" />
          <h1>Organisation settings</h1>
          <p>{org.name}</p>
          <Alert tone="info">
            This organisation is archived, so its profile is view-only.
          </Alert>
        </div>
      </div>
    );
  }

  return (
    <div className="iv-os-page">
      <div className="iv-os-topline">
        <Link href="/dashboard" className="iv-os-back">
          <ArrowLeft size={16} aria-hidden="true" />
          Back to dashboard
        </Link>
        <span className="iv-os-topline-tag">
          <span className="iv-os-status-dot" />
          Active workspace
        </span>
      </div>

      <div className="iv-os-page-heading">
        <div>
          <div className="iv-os-eyebrow">
            <span className="iv-os-gold-dot" />
            WORKSPACE MANAGEMENT
          </div>
          <h1>
            Organisation <span>settings.</span>
          </h1>
          <p>
            Manage your organisation&apos;s identity, business
            information and financial preferences.
          </p>
        </div>
        <div className="iv-os-heading-icon" aria-hidden="true">
          <Building2 size={30} strokeWidth={1.5} />
        </div>
      </div>

      <div className="iv-os-layout">
        <div className="iv-os-content">
          <SettingsForm
            key={org.id}
            org={org}
            onSaved={(saved) =>
              setState((prev) =>
                prev.kind === "ready"
                  ? { ...prev, org: saved }
                  : prev,
              )
            }
          />
        </div>

        <aside className="iv-os-sidebar">
          <div className="iv-os-sidebar-inner">
            <div className="iv-os-identity-card">
              <div className="iv-os-identity-decoration" />
              <div className="iv-os-identity-top">
                <div className="iv-os-identity-icon">
                  <Building2 size={24} aria-hidden="true" />
                </div>
                <BadgeCheck size={20} className="iv-os-gold-icon" />
              </div>

              <span className="iv-os-identity-label">
                YOUR ORGANISATION
              </span>
              <h2>{org.name}</h2>
              <p>
                Your active InnoValuation workspace.
              </p>

              <div className="iv-os-identity-divider" />

              <div className="iv-os-identity-detail">
                <span>Workspace role</span>
                <strong>
                  {org.role.charAt(0).toUpperCase() +
                    org.role.slice(1)}
                </strong>
              </div>
              <div className="iv-os-identity-detail">
                <span>Currency</span>
                <strong>{org.currency}</strong>
              </div>
              <div className="iv-os-identity-detail">
                <span>Status</span>
                <strong className="iv-os-active-text">
                  <CheckCircle2 size={14} />
                  Active
                </strong>
              </div>
            </div>

            <div className="iv-os-help-card">
              <span className="iv-os-help-icon">
                <Sparkles size={20} aria-hidden="true" />
              </span>
              <h3>Make your profile complete</h3>
              <p>
                Keep your organisation details accurate so your team
                can work with consistent information.
              </p>
              <div className="iv-os-help-divider" />
              <div className="iv-os-help-point">
                <CheckCircle2 size={16} />
                Keep business details up to date
              </div>
              <div className="iv-os-help-point">
                <CheckCircle2 size={16} />
                Confirm your financial currency
              </div>
              <div className="iv-os-help-point">
                <CheckCircle2 size={16} />
                Maintain accurate contact details
              </div>
            </div>

            <Link
              href="/organisation/importance"
              className="iv-os-side-link"
            >
              <span className="iv-os-side-link-icon">
                <SlidersHorizontal
                  size={19}
                  aria-hidden="true"
                />
              </span>

              <span>
                <strong>Dimension importance</strong>
                <small>
                  Orders tied priorities; never changes a score or the IQ
                </small>
              </span>

              <ArrowUpRight
                size={18}
                aria-hidden="true"
              />
            </Link>

            <Link
              href="/organisation/activity"
              className="iv-os-side-link"
            >
              <span className="iv-os-side-link-icon">
                <History
                  size={19}
                  aria-hidden="true"
                />
              </span>

              <span>
                <strong>Activity log</strong>
                <small>
                  Who did what, and when; entries cannot be changed
                </small>
              </span>

              <ArrowUpRight
                size={18}
                aria-hidden="true"
              />
            </Link>

            <Link href="/team" className="iv-os-side-link">
              <span className="iv-os-side-link-icon">
                <UsersRound size={19} aria-hidden="true" />
              </span>
              <span>
                <strong>Manage your team</strong>
                <small>Members and permissions</small>
              </span>
              <ArrowUpRight size={18} aria-hidden="true" />
            </Link>
          </div>
        </aside>
      </div>
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
  const [description, setDescription] = useState(
    org.description ?? "",
  );
  const [industry, setIndustry] = useState(org.industry ?? "");
  const [country, setCountry] = useState(org.country ?? "");
  const [sizeBand, setSizeBand] = useState(org.size_band ?? "");
  const [revenueBand, setRevenueBand] = useState(
    org.revenue_band ?? "",
  );
  const [founderNames, setFounderNames] = useState(
    org.founder_names ?? "",
  );
  const [website, setWebsite] = useState(org.website ?? "");
  const [contactName, setContactName] = useState(
    org.primary_contact_name ?? "",
  );
  const [contactEmail, setContactEmail] = useState(
    org.primary_contact_email ?? "",
  );
  const [currency, setCurrency] = useState(org.currency);
  const [nameError, setNameError] = useState<string | undefined>();
  const [saved, setSaved] = useState(false);
  const [dirty, setDirty] = useState(false);

  function markChanged() {
    setDirty(true);
    setSaved(false);
  }

  async function handleSubmit(event: FormEvent) {
    event.preventDefault();
    setSaved(false);

    if (!name.trim()) {
      setNameError("Enter the organisation's name.");
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
        currency,
      }),
    );

    if (result) {
      onSaved(result);
      setSaved(true);
      setDirty(false);
      await refresh();
    }
  }

  return (
    <form
      onSubmit={(event) => void handleSubmit(event)}
      noValidate
      className="iv-os-form"
    >
      {error && <Alert tone="error">{error.message}</Alert>}
      {saved && <Alert tone="success">Saved.</Alert>}

      <section className="iv-os-panel">
        <SectionHeading
          icon={<Building2 size={22} />}
          eyebrow="01 / ORGANISATION IDENTITY"
          title="Company profile"
          description="The essential details that define your organisation."
        />

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
                markChanged();
              }}
            />
          </Field>

          <Field wide>
            <TextField
              label="Description"
              name="description"
              value={description}
              onChange={(event) => {
                setDescription(event.target.value);
                markChanged();
              }}
            />
          </Field>

          <Field>
            <TextField
              label="Industry"
              name="industry"
              value={industry}
              onChange={(event) => {
                setIndustry(event.target.value);
                markChanged();
              }}
            />
          </Field>

          <Field>
            <TextField
              label="Country"
              name="country"
              maxLength={2}
              hint="2-letter code, e.g. US."
              value={country}
              onChange={(event) => {
                setCountry(event.target.value);
                markChanged();
              }}
            />
          </Field>

          <Field>
            <TextField
              label="Company size"
              name="size_band"
              hint="e.g. 11 to 50 people."
              value={sizeBand}
              onChange={(event) => {
                setSizeBand(event.target.value);
                markChanged();
              }}
            />
          </Field>

          <Field>
            <TextField
              label="Revenue band"
              name="revenue_band"
              hint="e.g. 1M to 10M."
              value={revenueBand}
              onChange={(event) => {
                setRevenueBand(event.target.value);
                markChanged();
              }}
            />
          </Field>

          <Field wide>
            <TextField
              label="Founders"
              name="founder_names"
              value={founderNames}
              onChange={(event) => {
                setFounderNames(event.target.value);
                markChanged();
              }}
            />
          </Field>
        </div>
      </section>

      <section className="iv-os-panel">
        <SectionHeading
          icon={<Globe2 size={22} />}
          eyebrow="02 / DIGITAL PRESENCE"
          title="Online presence"
          description="Connect your organisation's public digital identity."
        />

        <div className="iv-os-fields">
          <Field wide>
            <TextField
              label="Website"
              type="url"
              name="website"
              hint="Full address, e.g. https://example.com."
              value={website}
              onChange={(event) => {
                setWebsite(event.target.value);
                markChanged();
              }}
            />
          </Field>
        </div>
      </section>

      <section className="iv-os-panel">
        <SectionHeading
          icon={<ContactRound size={22} />}
          eyebrow="03 / BUSINESS CONTACT"
          title="Primary contact"
          description="Keep a reliable point of contact for your organisation."
        />

        <div className="iv-os-fields">
          <Field>
            <TextField
              label="Primary contact name"
              name="primary_contact_name"
              value={contactName}
              onChange={(event) => {
                setContactName(event.target.value);
                markChanged();
              }}
            />
          </Field>

          <Field>
            <TextField
              label="Primary contact email"
              type="email"
              name="primary_contact_email"
              value={contactEmail}
              onChange={(event) => {
                setContactEmail(event.target.value);
                markChanged();
              }}
            />
          </Field>
        </div>
      </section>

      <section className="iv-os-panel">
        <SectionHeading
          icon={<CircleDollarSign size={22} />}
          eyebrow="04 / FINANCIAL PREFERENCES"
          title="Reporting currency"
          description="Choose the currency used when presenting financial information."
        />

        <div className="iv-os-fields">
          <Field wide>
            <div className="iv-os-currency">
              <CurrencySelect
                value={currency}
                onChange={(next) => {
                  setCurrency(next);
                  markChanged();
                }}
                hint="Investments and Value for Money are shown in this currency."
              />
            </div>
          </Field>
        </div>

        <div className="iv-os-info-note">
          <Info size={17} aria-hidden="true" />
          <span>
            This setting controls how applicable financial values
            are displayed in your workspace.
          </span>
        </div>
      </section>

      <div className="iv-os-save-panel">
        <div className="iv-os-save-copy">
          <span className="iv-os-save-icon">
            {saved ? (
              <CheckCircle2 size={21} />
            ) : (
              <ShieldCheck size={21} />
            )}
          </span>
          <div>
            <strong>
              {saved
                ? "Your changes are saved"
                : dirty
                  ? "You have unsaved changes"
                  : "Organisation details"}
            </strong>
            <p>
              {saved
                ? "Your organisation profile has been updated."
                : "Review your information before saving."}
            </p>
          </div>
        </div>

        <Button type="submit" busy={busy}>
          <span className="iv-os-button-content">
            <Save size={17} aria-hidden="true" />
            Save changes
            <ChevronRight size={16} aria-hidden="true" />
          </span>
        </Button>
      </div>

      <div className="iv-os-bottom-caption">
        <Layers3 size={15} aria-hidden="true" />
        Changes are applied to the active organisation.
      </div>
    </form>
  );
}

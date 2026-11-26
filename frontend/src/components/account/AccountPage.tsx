
"use client";

import { useState } from "react";
import type { FormEvent, InputHTMLAttributes, ReactNode } from "react";
import {
  ArrowRight,
  BadgeCheck,
  Check,
  CheckCircle2,
  CircleHelp,
  Eye,
  EyeOff,
  Fingerprint,
  KeyRound,
  LockKeyhole,
  Mail,
  Save,
  ShieldCheck,
  Sparkles,
  UserRound,
} from "lucide-react";

import { useMe } from "@/components/app/me-context";
import { Alert } from "@/components/ui/Alert";
import { changePassword, updateName } from "@/lib/api/me";
import { newPasswordError, useSubmit } from "@/lib/forms";

type AccountFieldProps = Omit<
  InputHTMLAttributes<HTMLInputElement>,
  "id"
> & {
  label: string;
  name: string;
  icon: ReactNode;
  hint?: string;
  error?: string;
  trailing?: ReactNode;
};

function AccountField({
  label,
  name,
  icon,
  hint,
  error,
  trailing,
  className = "",
  ...props
}: AccountFieldProps) {
  const errorId = `${name}-error`;
  const hintId = `${name}-hint`;

  return (
    <div className="iv-account-field">
      <label
        htmlFor={name}
        className="iv-account-label"
      >
        {label}
        {props.required && (
          <span className="iv-account-required" aria-hidden="true">
            *
          </span>
        )}
      </label>

      <div
        className={`iv-account-input-wrap ${props.disabled ? "iv-account-input-disabled" : ""
          } ${error ? "iv-account-input-error" : ""}`}
      >
        <span className="iv-account-input-icon" aria-hidden="true">
          {icon}
        </span>

        <input
          {...props}
          id={name}
          name={name}
          aria-label={label}
          className={`iv-account-input ${className}`}
          aria-invalid={error ? true : undefined}
          aria-describedby={
            error ? errorId : hint ? hintId : undefined
          }
        />

        {trailing && (
          <span className="iv-account-input-trailing">
            {trailing}
          </span>
        )}
      </div>

      {error ? (
        <p id={errorId} className="iv-account-field-error">
          {error}
        </p>
      ) : hint ? (
        <p id={hintId} className="iv-account-field-hint">
          {hint}
        </p>
      ) : null}
    </div>
  );
}

function PasswordVisibility({
  visible,
  onToggle,
  label,
}: {
  visible: boolean;
  onToggle: () => void;
  label: string;
}) {
  return (
    <button
      type="button"
      className="iv-account-visibility"
      onClick={onToggle}
      aria-label={`${visible ? "Hide" : "Show"} ${label}`}
      aria-pressed={visible}
      title={`${visible ? "Hide" : "Show"} ${label}`}
    >
      {visible ? (
        <EyeOff size={18} strokeWidth={1.8} />
      ) : (
        <Eye size={18} strokeWidth={1.8} />
      )}
    </button>
  );
}

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
    <div className="iv-account-section-heading">
      <div className="iv-account-section-icon" aria-hidden="true">
        {icon}
      </div>

      <div className="iv-account-section-copy">
        <p className="iv-account-eyebrow">{eyebrow}</p>
        <h2>{title}</h2>
        <p className="iv-account-section-description">
          {description}
        </p>
      </div>
    </div>
  );
}

function ProfileCard() {
  const { me, update } = useMe();
  const { busy, error, run } = useSubmit();

  const [name, setName] = useState(me.name);
  const [saved, setSaved] = useState(false);

  const changed = name !== me.name;

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setSaved(false);

    const result = await run(() => updateName(name));

    if (result) {
      update(result);
      setSaved(true);
    }
  }

  return (
    <section className="iv-account-card iv-account-profile-card">
      <SectionHeading
        eyebrow="PERSONAL INFORMATION"
        title="Profile details"
        description="Manage how your name appears across your InnoValuation workspace."
        icon={<UserRound size={22} strokeWidth={1.8} />}
      />

      <div className="iv-account-card-body">
        <form
          onSubmit={(event) => void handleSubmit(event)}
          className="iv-account-form"
          noValidate
        >
          {error && <Alert tone="error">{error.message}</Alert>}

          {saved && (
            <Alert tone="success">
              Your name is saved.
            </Alert>
          )}

          <AccountField
            label="Name"
            name="name"
            type="text"
            autoComplete="name"
            icon={<UserRound size={19} />}
            required
            value={name}
            onChange={(event) => {
              setName(event.target.value);
              setSaved(false);
            }}
            placeholder="Enter your full name"
          />

          <AccountField
            label="Email"
            name="email"
            type="email"
            autoComplete="email"
            icon={<Mail size={19} />}
            value={me.email}
            disabled
            readOnly
            trailing={<LockKeyhole size={16} />}
            hint="Your email address is managed by your account."
          />

          <div className="iv-account-form-footer">
            <p className="iv-account-footer-note">
              <ShieldCheck size={16} aria-hidden="true" />
              Your profile is associated with your account.
            </p>

            <button
              type="submit"
              disabled={busy}
              className="iv-account-primary-button"
            >
              {busy ? (
                <span className="iv-account-spinner" aria-hidden="true" />
              ) : saved && !changed ? (
                <Check size={18} aria-hidden="true" />
              ) : (
                <Save size={18} aria-hidden="true" />
              )}

              <span>Save</span>
            </button>
          </div>
        </form>
      </div>
    </section>
  );
}

function PasswordCard() {
  const { busy, error, run } = useSubmit();

  const [current, setCurrent] = useState("");
  const [next, setNext] = useState("");

  const [showCurrent, setShowCurrent] = useState(false);
  const [showNext, setShowNext] = useState(false);

  const [nextError, setNextError] = useState<string | undefined>(
    undefined,
  );

  const [doneMessage, setDoneMessage] = useState<string | null>(null);

  const passwordLongEnough = next.length >= 8;

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setDoneMessage(null);

    const invalid = newPasswordError(next);

    if (invalid) {
      setNextError(invalid);
      return;
    }

    const result = await run(() => changePassword(current, next));

    if (result) {
      setDoneMessage(result.message);
      setCurrent("");
      setNext("");
      setNextError(undefined);
      setShowCurrent(false);
      setShowNext(false);
    }
  }

  return (
    <section className="iv-account-card iv-account-security-card">
      <SectionHeading
        eyebrow="ACCOUNT SECURITY"
        title="Change password"
        description="Update your password to help protect access to your workspace."
        icon={<KeyRound size={22} strokeWidth={1.8} />}
      />

      <div className="iv-account-card-body">
        <div className="iv-account-security-notice">
          <span className="iv-account-notice-icon">
            <ShieldCheck size={20} />
          </span>

          <div>
            <strong>Security reminder</strong>
            <p>
              Changing your password signs you out everywhere else.
            </p>
          </div>
        </div>

        <form
          onSubmit={(event) => void handleSubmit(event)}
          className="iv-account-form"
          noValidate
        >
          {error && <Alert tone="error">{error.message}</Alert>}

          {doneMessage && (
            <Alert tone="success">{doneMessage}</Alert>
          )}

          <AccountField
            label="Current password"
            name="current_password"
            type={showCurrent ? "text" : "password"}
            autoComplete="current-password"
            icon={<LockKeyhole size={19} />}
            required
            value={current}
            onChange={(event) => setCurrent(event.target.value)}
            placeholder="Enter your current password"
            trailing={
              <PasswordVisibility
                visible={showCurrent}
                onToggle={() => setShowCurrent((value) => !value)}
                label="current password"
              />
            }
          />

          <AccountField
            label="New password"
            name="new_password"
            type={showNext ? "text" : "password"}
            autoComplete="new-password"
            icon={<KeyRound size={19} />}
            required
            minLength={8}
            error={nextError}
            value={next}
            onChange={(event) => {
              const value = event.target.value;
              setNext(value);
              setDoneMessage(null);

              setNextError((previous) =>
                previous ? newPasswordError(value) : undefined,
              );
            }}
            placeholder="Create your new password"
            trailing={
              <PasswordVisibility
                visible={showNext}
                onToggle={() => setShowNext((value) => !value)}
                label="new password"
              />
            }
          />

          <div className="iv-account-password-guidance">
            <span
              className={`iv-account-requirement-icon ${passwordLongEnough
                ? "iv-account-requirement-met"
                : ""
                }`}
            >
              {passwordLongEnough ? (
                <Check size={14} aria-hidden="true" />
              ) : (
                <CircleHelp size={14} aria-hidden="true" />
              )}
            </span>

            <span>
              Use at least 8 characters for your new password.
            </span>
          </div>

          <div className="iv-account-form-footer">
            <p className="iv-account-footer-note">
              <Fingerprint size={17} aria-hidden="true" />
              Choose a unique password you do not reuse.
            </p>

            <button
              type="submit"
              disabled={busy}
              className="iv-account-primary-button"
            >
              {busy ? (
                <span className="iv-account-spinner" aria-hidden="true" />
              ) : (
                <LockKeyhole size={18} aria-hidden="true" />
              )}
              <span>Change password</span>
              {!busy && <ArrowRight size={17} aria-hidden="true" />}
            </button>
          </div>
        </form>
      </div>
    </section>
  );
}

export function AccountPage() {
  const { me } = useMe();

  const initials =
    me.name
      .trim()
      .split(/\s+/)
      .filter(Boolean)
      .slice(0, 2)
      .map((part) => part.charAt(0).toUpperCase())
      .join("") || "U";

  return (
    <div className="iv-account-page">
      <div className="iv-account-page-intro">
        <div>
          <p className="iv-account-top-label">
            <span className="iv-account-label-dot" />
            YOUR WORKSPACE IDENTITY
          </p>

          <h1>Account settings<span>.</span></h1>

          <p className="iv-account-page-subtitle">
            Your personal profile and account security, all in one place.
          </p>
        </div>

        <div className="iv-account-heading-tag">
          <ShieldCheck size={16} aria-hidden="true" />
          Personal settings
        </div>
      </div>

      <section className="iv-account-hero" aria-label="Account overview">
        <div className="iv-account-hero-pattern" aria-hidden="true" />

        <div className="iv-account-hero-content">
          <div className="iv-account-hero-avatar">
            {initials}
          </div>

          <div className="iv-account-hero-person">
            <p className="iv-account-hero-eyebrow">
              <Sparkles size={14} aria-hidden="true" />
              YOUR INNOVALUATION ACCOUNT
            </p>

            <h2>{me.name}</h2>

            <p className="iv-account-hero-email">
              <Mail size={15} aria-hidden="true" />
              <span>{me.email}</span>
            </p>
          </div>
        </div>

        <div className="iv-account-hero-decoration" aria-hidden="true">
          <div className="iv-account-orbit iv-account-orbit-one" />
          <div className="iv-account-orbit iv-account-orbit-two" />
          <div className="iv-account-orbit-center">
            <Fingerprint size={35} strokeWidth={1.2} />
          </div>
        </div>

        <span className="iv-account-hero-corner" aria-hidden="true">
          <BadgeCheck size={15} />
          Account profile
        </span>
      </section>

      <div className="iv-account-content-grid">
        <div className="iv-account-main-column">
          <ProfileCard />
          <PasswordCard />
        </div>

        <aside className="iv-account-aside">
          <div className="iv-account-aside-card">
            <div className="iv-account-aside-icon">
              <ShieldCheck size={24} strokeWidth={1.7} />
            </div>

            <p className="iv-account-aside-eyebrow">
              ACCOUNT GUIDANCE
            </p>

            <h2>Keep your account protected.</h2>

            <p className="iv-account-aside-description">
              A few good habits can help you protect your
              workspace and personal information.
            </p>

            <div className="iv-account-aside-divider" />

            <div className="iv-account-tip">
              <CheckCircle2 size={19} aria-hidden="true" />
              <div>
                <strong>Use unique credentials</strong>
                <p>
                  Avoid reusing a password from another service.
                </p>
              </div>
            </div>

            <div className="iv-account-tip">
              <CheckCircle2 size={19} aria-hidden="true" />
              <div>
                <strong>Check your account details</strong>
                <p>
                  Keep your profile accurate and up to date.
                </p>
              </div>
            </div>

            <div className="iv-account-tip">
              <CheckCircle2 size={19} aria-hidden="true" />
              <div>
                <strong>Be mindful of shared devices</strong>
                <p>
                  Sign out when using a computer that others can access.
                </p>
              </div>
            </div>
          </div>

          <div className="iv-account-aside-footer">
            <Fingerprint size={19} aria-hidden="true" />
            <span>
              Your personal account is separate from your
              organisation&apos;s profile.
            </span>
          </div>
        </aside>
      </div>
    </div>
  );
}

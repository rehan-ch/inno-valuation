
"use client";

import {
  useEffect,
  useId,
  useRef,
  useState,
} from "react";
import {
  Building2,
  Check,
  ChevronDown,
  LoaderCircle,
  ShieldCheck,
} from "lucide-react";

import { useMe } from "@/components/app/me-context";
import { ApiError } from "@/lib/api/client";
import { setActiveOrganisation } from "@/lib/api/me";

export function OrgSwitcher() {
  const { me, update } = useMe();
  const id = useId();
  const containerRef = useRef<HTMLDivElement>(null);
  const triggerRef = useRef<HTMLButtonElement>(null);
  const menuRef = useRef<HTMLDivElement>(null);

  const [open, setOpen] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  // Set when a switch lands. The trigger is disabled while busy and cannot take focus,
  // so focus returns to it once it is enabled again rather than falling to the body.
  const refocus = useRef(false);

  const memberships = me.memberships;
  const consulting = me.consultant_organisations;

  const options = [...memberships, ...consulting];

  const current = options.find(
    (item) =>
      item.organisation_id === me.active_organisation_id
  );

  const currentName =
    current?.organisation_name ?? "Choose organisation";

  useEffect(() => {
    if (!open) return;

    function closeOutside(event: PointerEvent) {
      if (
        containerRef.current &&
        !containerRef.current.contains(event.target as Node)
      ) {
        setOpen(false);
      }
    }

    function handleEscape(event: KeyboardEvent) {
      if (event.key === "Escape") {
        setOpen(false);
        triggerRef.current?.focus();
      }
    }

    document.addEventListener("pointerdown", closeOutside);
    document.addEventListener("keydown", handleEscape);

    return () => {
      document.removeEventListener("pointerdown", closeOutside);
      document.removeEventListener("keydown", handleEscape);
    };
  }, [open]);

  useEffect(() => {
    if (busy || !refocus.current) return;
    refocus.current = false;
    triggerRef.current?.focus();
  }, [busy]);

  if (options.length === 0) return null;

  async function choose(organisationId: string) {
    if (
      !organisationId ||
      organisationId === me.active_organisation_id ||
      busy
    ) {
      setOpen(false);
      triggerRef.current?.focus();
      return;
    }

    setBusy(true);
    setError(null);

    try {
      const updatedMe = await setActiveOrganisation(
        organisationId
      );

      update(updatedMe);
      setOpen(false);
      refocus.current = true;
    } catch (err) {
      setError(
        err instanceof ApiError
          ? err.message
          : "Unable to switch organisation. Please try again."
      );
    } finally {
      setBusy(false);
    }
  }

  function handleTriggerKeyDown(
    event: React.KeyboardEvent<HTMLButtonElement>
  ) {
    if (
      !open &&
      (event.key === "ArrowDown" || event.key === "ArrowUp")
    ) {
      event.preventDefault();
      setOpen(true);
      requestAnimationFrame(() => {
        const buttons =
          menuRef.current?.querySelectorAll<HTMLButtonElement>(
            "button:not(:disabled)"
          );

        if (!buttons?.length) return;

        const target =
          event.key === "ArrowUp"
            ? buttons[buttons.length - 1]
            : buttons[0];

        target?.focus();
      });
    }
  }

  function handleMenuKeyDown(
    event: React.KeyboardEvent<HTMLDivElement>
  ) {
    if (
      event.key !== "ArrowDown" &&
      event.key !== "ArrowUp" &&
      event.key !== "Home" &&
      event.key !== "End"
    ) {
      return;
    }

    event.preventDefault();

    const buttons = Array.from(
      menuRef.current?.querySelectorAll<HTMLButtonElement>(
        "button:not(:disabled)"
      ) ?? []
    );

    if (!buttons.length) return;

    const index = buttons.findIndex(
      (button) => button === document.activeElement
    );

    let next = 0;

    if (event.key === "ArrowDown") {
      next = (index + 1) % buttons.length;
    } else if (event.key === "ArrowUp") {
      next = (index - 1 + buttons.length) % buttons.length;
    } else if (event.key === "End") {
      next = buttons.length - 1;
    }

    buttons[next]?.focus();
  }

  function renderOption(
    organisation: (typeof options)[number],
    isConsultant: boolean
  ) {
    const selected =
      organisation.organisation_id ===
      me.active_organisation_id;

    const Icon = isConsultant
      ? ShieldCheck
      : Building2;

    return (
      <button
        key={`${isConsultant ? "consultant" : "member"}-${organisation.organisation_id}`}
        type="button"
        disabled={busy}
        onClick={() =>
          void choose(organisation.organisation_id)
        }
        className={`
          group flex w-full items-center gap-3
          rounded-xl px-3 py-3 text-left
          transition-colors duration-200
          focus-visible:outline-2
          focus-visible:outline-offset-[-2px]
          focus-visible:outline-[#DFB96B]
          disabled:cursor-wait
          ${selected
            ? "bg-[#DFB96B]/12"
            : "hover:bg-white/[0.07]"
          }
        `}
      >
        <span
          className={`
            flex size-10 shrink-0 items-center
            justify-center rounded-xl border
            ${selected
              ? "border-[#DFB96B]/40 bg-[#DFB96B]/15 text-[#DFB96B]"
              : "border-white/10 bg-white/[0.05] text-[#A6B7D0]"
            }
          `}
        >
          <Icon size={18} strokeWidth={1.8} />
        </span>

        <span className="min-w-0 flex-1">
          <span
            className={`block truncate text-[13px] font-semibold ${selected ? "text-[#F1D397]" : "text-white"
              }`}
          >
            {organisation.organisation_name}
          </span>

          <span className="mt-0.5 block text-[11px] text-[#9FAFC6]">
            {isConsultant
              ? "Consulting access"
              : "Organisation workspace"}
          </span>
        </span>

        {selected && (
          <span
            className="flex size-6 shrink-0 items-center justify-center rounded-full bg-[#DFB96B] text-[#071426]"
            aria-label="Current organisation"
          >
            <Check size={14} strokeWidth={2.5} />
          </span>
        )}
      </button>
    );
  }

  return (
    <div
      ref={containerRef}
      className="iv-org-switcher relative w-full min-w-0"
    >
      <button
        ref={triggerRef}
        id={id}
        type="button"
        disabled={busy}
        aria-label={`Organisation: ${currentName}`}
        aria-haspopup="true"
        aria-expanded={open}
        aria-controls={`${id}-menu`}
        onClick={() => setOpen((previous) => !previous)}
        onKeyDown={handleTriggerKeyDown}
        className={`
          group relative flex h-11 w-full
          min-w-0 items-center gap-2.5
          rounded-xl border px-3.5
          text-left transition-all duration-200
          focus-visible:outline-2
          focus-visible:outline-offset-2
          focus-visible:outline-[#DFB96B]
          disabled:cursor-wait disabled:opacity-70
          ${open
            ? "border-[#DFB96B] bg-[#1B2C45] shadow-[0_0_0_3px_rgba(223,185,107,0.09)]"
            : "border-[#354861] bg-[#14253D] hover:border-[#DFB96B]/65 hover:bg-[#1B2C45]"
          }
        `}
      >
        <Building2
          size={17}
          strokeWidth={1.8}
          className="shrink-0 text-[#DFB96B]"
          aria-hidden="true"
        />

        <span className="min-w-0 flex-1 truncate text-[12px] font-semibold text-white sm:text-[13px]">
          {currentName}
        </span>

        {busy ? (
          <LoaderCircle
            size={15}
            className="shrink-0 animate-spin text-[#DFB96B]"
            aria-hidden="true"
          />
        ) : (
          <ChevronDown
            size={15}
            strokeWidth={1.8}
            aria-hidden="true"
            className={`shrink-0 text-[#DFB96B] transition-transform duration-200 ${open ? "rotate-180" : ""
              }`}
          />
        )}
      </button>

      {open && (
        <div
          id={`${id}-menu`}
          ref={menuRef}
          onKeyDown={handleMenuKeyDown}
          className="
            absolute left-0 top-[calc(100%+10px)]
            z-[100] w-full min-w-[245px]
            overflow-hidden rounded-2xl
            border border-[#34465F]
            bg-[#0C1B30]
            p-2
            shadow-[0_22px_60px_rgba(0,0,0,0.34)]
            motion-safe:animate-[iv-org-enter_180ms_ease-out_both]
            sm:left-auto sm:right-0 sm:w-[290px]
          "
        >
          <div className="px-3 pb-3 pt-2">
            <p className="text-[10px] font-bold uppercase tracking-[0.16em] text-[#DFB96B]">
              Switch workspace
            </p>
            <p className="mt-1 text-xs leading-5 text-[#9FAFC6]">
              Select an organisation to continue.
            </p>
          </div>

          {memberships.length > 0 && (
            <div>
              <p className="px-3 py-2 text-[10px] font-semibold uppercase tracking-[0.12em] text-[#8194AE]">
                Your organisations
              </p>

              <div className="space-y-1">
                {memberships.map((organisation) =>
                  renderOption(organisation, false)
                )}
              </div>
            </div>
          )}

          {consulting.length > 0 && (
            <div className={memberships.length ? "mt-3 border-t border-white/10 pt-3" : ""}>
              <p className="px-3 py-2 text-[10px] font-semibold uppercase tracking-[0.12em] text-[#8194AE]">
                Consulting access
              </p>

              <div className="space-y-1">
                {consulting.map((organisation) =>
                  renderOption(organisation, true)
                )}
              </div>
            </div>
          )}

          <div className="mt-2 border-t border-white/10 px-3 py-3">
            <p className="flex items-center gap-2 text-[11px] text-[#9FAFC6]">
              <ShieldCheck
                size={13}
                className="text-[#DFB96B]"
                aria-hidden="true"
              />
              Your workspace selection is secure.
            </p>
          </div>
        </div>
      )}

      {error && (
        <p
          role="alert"
          className="mt-2 max-w-[290px] rounded-lg border border-red-500/30 bg-red-950/80 px-3 py-2 text-xs leading-5 text-red-200"
        >
          {error}
        </p>
      )}
    </div>
  );
}

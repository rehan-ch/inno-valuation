"""Fill the local stack with a demo company: ``bin/seed-demo`` (development only).

Accounts are written straight to the database, already verified, so no email is sent.
Everything after that goes through the running API exactly as the screens do: two readiness
assessments (three people answer, the owner agrees and finalises), ideas scored by the AI
touchpoint and confirmed by their owners, dimension importance, targets and consultant
access. So the numbers on screen are the scoring engine's, not written by this script.

The only direct edit after the flows is to move the first readiness result and the first
scoring of one idea a few weeks into the past, so the history has dates to show.

Refuses to run unless ``ENVIRONMENT=development``. Running it again adds nothing;
``--reset`` removes the demo company and its accounts first.
"""
# ruff: noqa: T201 (a command-line tool: it prints)

import argparse
import random
import sys
import time
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any, Final

import httpx2
from sqlalchemy import delete, make_url, select, update

from app.core.security import hash_password
from app.core.sessions import CSRF_COOKIE, CSRF_HEADER
from app.core.settings import get_settings
from app.db.session import SessionLocal
from app.models import (
    AuditEvent,
    ConsultantGrant,
    IqAssessment,
    Membership,
    Organisation,
    ReadinessAssessment,
    ReadinessResult,
    SignInThrottle,
    User,
)
from app.models.enums import MembershipRole
from app.scoring.question_set import QUESTION_SET
from app.services.audit import AuditAction, record

LOCAL_HOSTS: Final = frozenset({"localhost", "127.0.0.1", "::1"})
PASSWORD: Final = "demo-compass-2026"  # noqa: S105 (a local demo account, printed on purpose)
ORGANISATION: Final = "Northwind Outfitters"
OWNER_EMAIL: Final = "dana@northwind.example"
PEOPLE: Final = (
    (OWNER_EMAIL, "Dana Okafor", MembershipRole.OWNER),
    ("marcus@northwind.example", "Marcus Lind", MembershipRole.ADMIN),
    ("priya@northwind.example", "Priya Raman", MembershipRole.MEMBER),
    ("tomas@northwind.example", "Tomas Vega", MembershipRole.COMMITTEE),
    ("ines@northwind.example", "Ines Duarte", MembershipRole.INVESTOR),
)
CONSULTANT: Final = ("amy@consultant.example", "Amy-Renee (consultant)")

# How strong the company is on each dimension, in book order (the middle of its answers,
# 1 to 5), for the first assessment and the one two months later.
EARLIER_LEVELS: Final = (3.4, 2.6, 2.2, 3.6, 3.8, 2.8, 2.4, 3.2, 3.0, 2.0, 1.8, 3.4)
LATER_LEVELS: Final = (3.8, 3.0, 2.4, 3.8, 4.2, 3.4, 3.2, 3.4, 3.2, 2.4, 2.6, 3.4)

IDEAS: Final[tuple[dict[str, Any], ...]] = (
    {
        "title": "Gear rental subscription",
        "summary": (
            "A monthly subscription that lets customers borrow tents, packs and climbing "
            "gear instead of buying them, with delivery to the trailhead and repair included."
        ),
        "problem": (
            "Most customers use expensive outdoor gear a few times a year, and many "
            "newcomers never start because of the upfront cost."
        ),
        "target_market": "City hikers and families aged 25 to 45 who camp 2 to 6 times a year.",
        "uniqueness": (
            "Combines our repair workshop, store network and customer data: gear is matched "
            "to the trip, and returned gear is refurbished and resold."
        ),
        "team": "Rental lead, two repair technicians, a logistics partner and the app team.",
        "risks": "Gear damage and loss, seasonal demand, and cannibalising full-price sales.",
        "stage": "pilot",
        "investment": "180000.00",
        "expected_value": "950000.00",
    },
    {
        "title": "AI trip planner in the app",
        "summary": (
            "A planner that builds a packing list and route from the customer's trip, "
            "weather and past purchases, and adds missing items to the basket."
        ),
        "problem": "Customers do not know what a trip needs and buy too much or too little.",
        "target_market": "Existing app users planning a trip in the next 30 days.",
        "uniqueness": "Uses our own product reviews and return data, which rivals lack.",
        "stage": "prototype",
        "investment": "95000.00",
        "expected_value": "400000.00",
    },
    {
        "title": "Repair and resale counter",
        "summary": (
            "A counter in every store where customers bring worn gear to be repaired, "
            "traded in or resold as certified second-hand."
        ),
        "problem": "Good gear is thrown away for small faults; thrifty customers shop elsewhere.",
        "target_market": "Existing customers and second-hand buyers near our 14 stores.",
        "stage": "concept",
        "investment": "60000.00",
        "expected_value": "220000.00",
    },
    {
        "title": "Guided weekend micro-adventures",
        "summary": "Short guided trips for beginners, sold with a rental kit and a store discount.",
        "stage": "idea",
        "investment": "25000.00",
    },
)


class Api:
    """Browser-like sessions against the running API, one per person: cookies, the CSRF
    header and the frontend's Origin on every request. Each person signs in once."""

    def __init__(self, base_url: str, origin: str) -> None:
        self._base_url = base_url
        self._origin = origin
        self._sessions: dict[str, httpx2.Client] = {}
        self._client: httpx2.Client | None = None

    def call(self, method: str, path: str, body: Any = None, *, ok: int = 200) -> Any:
        if self._client is None:
            raise SystemExit("Sign in first.")
        headers = {}
        token = self._client.cookies.get(CSRF_COOKIE)
        if token:
            headers[CSRF_HEADER] = token
        response = self._client.request(method, f"/api/v1{path}", json=body, headers=headers)
        if response.status_code != ok:
            raise SystemExit(
                f"{method} {path} answered {response.status_code}, expected {ok}: {response.text}"
            )
        return response.json()

    def sign_in(self, email: str, organisation_id: uuid.UUID) -> None:
        """Act as ``email`` from here on."""
        if email in self._sessions:
            self._client = self._sessions[email]
            return
        self._client = httpx2.Client(
            base_url=self._base_url, timeout=30, headers={"Origin": self._origin}
        )
        self._sessions[email] = self._client
        me = self.call("POST", "/auth/sign-in", {"email": email, "password": PASSWORD})
        if me["active_organisation_id"] != str(organisation_id):
            self.call("POST", "/me/active-organisation", {"organisation_id": str(organisation_id)})


def _accounts() -> tuple[uuid.UUID, bool]:
    """The demo people, their organisation and the consultant's access, written directly
    (verified, no email). Returns the organisation id and whether it was just created."""
    now = datetime.now(UTC)
    with SessionLocal() as db:
        owner = db.scalar(select(User).where(User.email == OWNER_EMAIL))
        if owner is not None:
            org_id = db.scalar(
                select(Membership.organisation_id).where(Membership.user_id == owner.id)
            )
            if org_id is not None:
                return org_id, False
        password_hash = hash_password(PASSWORD)
        users: dict[str, User] = {}
        for email, name, _role in (*PEOPLE, (*CONSULTANT, None)):
            user = db.scalar(select(User).where(User.email == email))
            if user is None:
                user = User(
                    email=email, name=name, password_hash=password_hash, email_verified_at=now
                )
                db.add(user)
            users[email] = user
        db.flush()
        owner = users[OWNER_EMAIL]
        org = Organisation(
            name=ORGANISATION,
            description="Outdoor clothing and equipment, 14 stores and an online shop.",
            industry="Retail",
            country="US",
            size_band="201-500",
            currency="USD",
            created_by_user_id=owner.id,
        )
        db.add(org)
        db.flush()
        for email, _name, role in PEOPLE:
            db.add(Membership(organisation_id=org.id, user_id=users[email].id, role=role))
        consultant = users[CONSULTANT[0]]
        db.add(
            ConsultantGrant(
                organisation_id=org.id,
                consultant_email=consultant.email,
                consultant_user_id=consultant.id,
                granted_by_user_id=owner.id,
                expires_at=now + timedelta(days=90),
                accepted_at=now,
            )
        )
        record(
            db,
            AuditAction.ORGANISATION_CREATED,
            actor=owner,
            organisation_id=org.id,
            target_type="organisation",
            target_id=org.id,
        )
        db.commit()
        return org.id, True


def _reset() -> None:
    """Remove the demo company and its accounts, so the next run starts clean."""
    emails = [email for email, _name, _role in PEOPLE] + [CONSULTANT[0]]
    with SessionLocal() as db:
        users = list(db.scalars(select(User).where(User.email.in_(emails))))
        org_ids = set(
            db.scalars(
                select(Membership.organisation_id).where(
                    Membership.user_id.in_([u.id for u in users])
                )
            )
        )
        for org in db.scalars(
            select(Organisation).where(
                Organisation.id.in_(org_ids), Organisation.name == ORGANISATION
            )
        ):
            db.execute(delete(AuditEvent).where(AuditEvent.organisation_id == org.id))
            db.delete(org)
        db.flush()
        for user in users:
            db.execute(delete(AuditEvent).where(AuditEvent.actor_user_id == user.id))
            db.delete(user)
        db.commit()


def _answers(levels: tuple[float, ...], rng: random.Random, spread: float) -> dict[str, int]:
    """One person's 60 answers: near the company's level on each dimension."""
    scale = QUESTION_SET.readiness_scale
    answers = {}
    for dimension, level in zip(QUESTION_SET.dimensions, levels, strict=True):
        for question in dimension.questions:
            answer = round(level + rng.uniform(-spread, spread))
            answers[question.id] = max(scale.min, min(scale.max, answer))
    return answers


def _readiness(api: Api, org_id: uuid.UUID, levels: tuple[float, ...], rng: random.Random) -> str:
    """Three people answer on their own; the owner agrees an answer per question (the
    middle one of the three) and finalises."""
    api.sign_in(OWNER_EMAIL, org_id)
    assessment_id: str = api.call("POST", "/readiness/assessments", ok=201)["id"]
    base = f"/readiness/assessments/{assessment_id}"
    everyone = []
    for email, _name, _role in PEOPLE[:3]:
        api.sign_in(email, org_id)
        answers = _answers(levels, rng, spread=1.1)
        api.call("PATCH", f"{base}/my-answers", {"answers": answers})
        api.call("POST", f"{base}/my-answers/submit")
        everyone.append(answers)
    api.sign_in(OWNER_EMAIL, org_id)
    api.call("POST", f"{base}/consensus/begin")
    agreed = {
        question_id: sorted(person[question_id] for person in everyone)[1]
        for question_id in QUESTION_SET.all_question_ids()
    }
    first = QUESTION_SET.all_question_ids()[0]
    api.call(
        "PATCH",
        f"{base}/consensus",
        {"answers": agreed, "notes": {first: "Agreed after comparing store and online feedback."}},
    )
    api.call("POST", f"{base}/finalise")
    return assessment_id


def _proposal(api: Api, idea_id: str) -> dict[str, Any]:
    """Send the idea for scoring and wait for the AI's proposal."""
    assessment: dict[str, Any] = api.call("POST", f"/ideas/{idea_id}/assessments", ok=201)
    deadline = time.monotonic() + 180
    while assessment["proposal_status"] == "pending":
        if time.monotonic() > deadline:
            raise SystemExit(
                "The scoring proposal did not arrive. Is the worker running (bin/dev)?"
            )
        time.sleep(1.5)
        assessment = api.call("GET", f"/ideas/{idea_id}/assessments/{assessment['id']}")
    if assessment["proposal_status"] != "ready":
        raise SystemExit("The scoring proposal failed. Check the worker log.")
    return assessment


def _confirm(
    api: Api,
    idea_id: str,
    assessment: dict[str, Any],
    final: tuple[int, ...],
    notes: dict[str, str],
) -> None:
    """The owner reviews the proposal: sets the score they stand behind on each dimension
    (book order), gives a reason where it matters, and confirms. A score equal to the
    proposal is left as proposed."""
    proposed = {d["key"]: d["proposed_score"] for d in assessment["dimensions"]}
    scores = {
        key: score
        for key, score in zip(QUESTION_SET.dimension_keys, final, strict=True)
        if proposed[key] != score
    }
    base = f"/ideas/{idea_id}/assessments/{assessment['id']}"
    if scores or notes:
        api.call("PATCH", f"{base}/review", {"scores": scores, "notes": notes})
    api.call("POST", f"{base}/confirm")


def _ideas(api: Api, org_id: uuid.UUID) -> tuple[str, str]:
    """Four ideas at different stages. Returns the first idea and its first assessment,
    which is then scored a second time."""
    api.sign_in("priya@northwind.example", org_id)
    rental: str = api.call("POST", "/ideas", IDEAS[0], ok=201)["id"]
    first = _proposal(api, rental)
    _confirm(
        api,
        rental,
        first,
        (7, 6, 5, 7, 6, 4, 5, 6, 7, 8, 4, 5),
        {
            "sustainable_future": "Refurbishing and reselling returned gear is central.",
            "financial_imperative": "The pilot has not shown the margin yet.",
            "data_intelligence": "Trip matching is still done by hand.",
        },
    )
    # Scored again after the pilot: most dimensions moved up a point.
    second = _proposal(api, rental)
    _confirm(
        api,
        rental,
        second,
        (8, 7, 6, 7, 7, 5, 5, 7, 7, 9, 5, 6),
        {
            "sustainable_future": "Pilot: 81% of returned gear was refurbished and resold.",
            "customer_journey": "Trailhead delivery scored 4.7 of 5 in the pilot survey.",
            "channel_navigation": "Bookable in the app and in all 14 stores.",
        },
    )

    api.sign_in("marcus@northwind.example", org_id)
    planner: str = api.call("POST", "/ideas", IDEAS[1], ok=201)["id"]
    _confirm(
        api,
        planner,
        _proposal(api, planner),
        (7, 5, 6, 6, 8, 5, 4, 4, 6, 3, 9, 5),
        {
            "data_intelligence": "Built on our own review and return data.",
            "sustainable_future": "No direct effect on our footprint.",
        },
    )

    api.sign_in(OWNER_EMAIL, org_id)
    counter: str = api.call("POST", "/ideas", IDEAS[2], ok=201)["id"]
    _proposal(api, counter)  # left for the owner to review during the demo
    api.call("POST", "/ideas", IDEAS[3], ok=201)  # a draft, not yet scored
    return rental, first["id"]


def _settings(api: Api, org_id: uuid.UUID) -> None:
    api.sign_in(OWNER_EMAIL, org_id)
    weights: dict[str, Any] = dict.fromkeys(QUESTION_SET.dimension_keys, 1)
    weights.update(sustainable_future=3, customer_journey=2)
    api.call("PUT", "/weights", {"weights": weights})
    api.call(
        "PUT",
        "/targets/readiness",
        {
            "targets": {
                "customer_journey": 22,
                "channel_navigation": 18,
                "organizational_agility": 20,
                "sustainable_future": 18,
                "data_intelligence": 20,
            }
        },
    )
    api.call(
        "PUT",
        "/targets/iq",
        {"targets": {"customer_journey": 8, "sustainable_future": 9, "financial_imperative": 7}},
    )


def _backdate(org_id: uuid.UUID, readiness_id: str, iq_assessment_id: str) -> None:
    """Move the first readiness result and the first scoring of the rental idea into the
    past, with their log entries, so the history shows a real interval."""
    with SessionLocal() as db:
        readiness = db.get(ReadinessAssessment, uuid.UUID(readiness_id))
        scoring = db.get(IqAssessment, uuid.UUID(iq_assessment_id))
        if readiness is None or scoring is None:
            return
        earlier = timedelta(days=63)
        readiness.created_at -= earlier
        if readiness.started_at is not None:
            readiness.started_at -= earlier
        if readiness.finalised_at is not None:
            readiness.finalised_at -= earlier
        db.execute(
            update(ReadinessResult)
            .where(ReadinessResult.assessment_id == readiness.id)
            .values(computed_at=ReadinessResult.computed_at - earlier)
        )
        pilot = timedelta(days=35)
        scoring.created_at -= pilot
        if scoring.confirmed_at is not None:
            scoring.confirmed_at -= pilot
        for target_id, shift in ((readiness.id, earlier), (scoring.id, pilot)):
            db.execute(
                update(AuditEvent)
                .where(AuditEvent.organisation_id == org_id, AuditEvent.target_id == target_id)
                .values(created_at=AuditEvent.created_at - shift)
            )
        # The sign-ins above count towards this machine's sign-in limit; give them back.
        db.execute(delete(SignInThrottle))
        db.commit()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--api", default="http://localhost:8000", help="the running API")
    parser.add_argument(
        "--reset", action="store_true", help="remove the demo company first, then add it again"
    )
    args = parser.parse_args()
    settings = get_settings()
    if settings.environment != "development":
        print(f"Refusing to seed: ENVIRONMENT is {settings.environment}, not development.")
        return 1
    database_host = make_url(settings.database_url).host
    if database_host not in LOCAL_HOSTS:
        print(f"Refusing to seed: the database is on {database_host}, not on this machine.")
        return 1

    if args.reset:
        _reset()
        print("Removed the earlier demo company.")
    with SessionLocal() as db:
        # Earlier runs and local testing may have used up this machine's sign-in limit.
        db.execute(delete(SignInThrottle))
        db.commit()
    org_id, created = _accounts()
    if created:
        api = Api(args.api, settings.frontend_origin)
        rng = random.Random(12)  # noqa: S311 (demo answers, not a secret)
        try:
            print("Readiness: the first assessment...")
            earlier = _readiness(api, org_id, EARLIER_LEVELS, rng)
            print("Readiness: the second assessment...")
            _readiness(api, org_id, LATER_LEVELS, rng)
            print("Ideas: scoring and confirming...")
            _rental, first_scoring = _ideas(api, org_id)
            _settings(api, org_id)
            _backdate(org_id, earlier, first_scoring)
        except (SystemExit, httpx2.HTTPError) as error:
            print(f"Stopped part-way: {error}")
            print("The demo company is incomplete. Run bin/seed-demo --reset to start again.")
            return 1
        print("Done.")
    else:
        print("The demo company is already there; nothing was added.")

    print(f"\n{ORGANISATION}  ·  password for every account: {PASSWORD}\n")
    for email, name, role in PEOPLE:
        print(f"  {role.value:<10} {email:<28} {name}")
    print(f"  {'consultant':<10} {CONSULTANT[0]:<28} {CONSULTANT[1]}")
    print(f"\nOpen {settings.frontend_origin}/sign-in")
    return 0


if __name__ == "__main__":
    sys.exit(main())

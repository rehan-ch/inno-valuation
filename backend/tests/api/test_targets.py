"""Targets per dimension over HTTP (spec 6; PROVISIONAL Q8).

A target is a wanted dimension score on one scale. It changes no score; the gap on results
is covered in test_dashboard.py. Earlier targets are kept as history.
"""

from datetime import UTC, datetime
from typing import Any

import httpx2
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import AuditEvent, DimensionTargets
from app.models.enums import MembershipRole, OrganisationStatus
from app.scoring.question_set import QUESTION_SET
from app.services.audit import AuditAction
from tests.api.flows import KEYS, as_user
from tests.api.helpers import csrf, member
from tests.factories import ConsultantGrantFactory, verified_user

BASE = "/api/v1/targets"


def _put(client: TestClient, scale: str, targets: dict[str, Any]) -> httpx2.Response:
    response: httpx2.Response = client.put(
        f"{BASE}/{scale}", json={"targets": targets}, headers=csrf(client)
    )
    return response


def _by_key(scale: dict[str, Any]) -> dict[str, int | None]:
    return {t["key"]: t["target"] for t in scale["targets"]}


def test_no_targets_until_someone_sets_them(client: TestClient) -> None:
    owner, org = member(MembershipRole.OWNER)
    as_user(client, owner, org)
    response = client.get(BASE)
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["question_set_version"] == QUESTION_SET.version
    assert body["can_change"] is True
    # The range of a target is the range of a dimension score on that scale.
    assert (body["readiness"]["minimum"], body["readiness"]["maximum"]) == (5, 25)
    assert (body["iq"]["minimum"], body["iq"]["maximum"]) == (1, 10)
    for scale in ("readiness", "iq"):
        assert [t["key"] for t in body[scale]["targets"]] == KEYS  # book order
        assert set(_by_key(body[scale]).values()) == {None}
        assert body[scale]["set_at"] is None
        assert body[scale]["set_by_name"] is None
    assert client.get(f"{BASE}/history").json() == []


def test_targets_are_set_per_scale_and_kept_apart(client: TestClient, db: Session) -> None:
    owner, org = member(MembershipRole.OWNER, name="Olive Owner")
    as_user(client, owner, org)

    response = _put(client, "readiness", {"customer_journey": 20, "data_intelligence": 25})
    assert response.status_code == 200, response.text
    body = response.json()
    readiness = _by_key(body["readiness"])
    assert readiness["customer_journey"] == 20
    assert readiness["data_intelligence"] == 25
    assert readiness["brand_magnetism"] is None
    assert body["readiness"]["set_by_name"] == "Olive Owner"
    assert body["readiness"]["set_at"] is not None
    assert set(_by_key(body["iq"]).values()) == {None}  # the other scale is untouched

    response = _put(client, "iq", {"customer_journey": 8})
    assert response.status_code == 200, response.text
    body = response.json()
    assert _by_key(body["iq"])["customer_journey"] == 8
    assert _by_key(body["readiness"])["customer_journey"] == 20

    rows = list(db.scalars(select(DimensionTargets).order_by(DimensionTargets.created_at)))
    assert [(r.scale.value, r.targets) for r in rows] == [
        ("readiness", {"customer_journey": 20, "data_intelligence": 25}),
        ("iq", {"customer_journey": 8}),
    ]
    assert {r.organisation_id for r in rows} == {org.id}
    assert {r.question_set_version for r in rows} == {QUESTION_SET.version}


def test_a_changed_target_keeps_the_earlier_one_in_history(client: TestClient) -> None:
    owner, org = member(MembershipRole.OWNER, name="Olive Owner")
    as_user(client, owner, org)
    _put(client, "readiness", {"customer_journey": 18, "brand_magnetism": 15})
    _put(client, "iq", {"customer_journey": 7})
    # Raise one, remove one (null and left out both mean no target), add one.
    changed = _put(
        client,
        "readiness",
        {"customer_journey": 22, "brand_magnetism": None, "financial_imperative": 20},
    )
    assert changed.status_code == 200, changed.text
    current = _by_key(changed.json()["readiness"])
    assert current["customer_journey"] == 22
    assert current["brand_magnetism"] is None
    assert current["financial_imperative"] == 20

    history = client.get(f"{BASE}/history").json()
    # Book order, not the alphabetical order the database keeps keys in.
    assert list(history[2]["targets"]) == ["customer_journey", "brand_magnetism"]
    assert [(h["scale"], h["targets"]) for h in history] == [  # newest first
        ("readiness", {"customer_journey": 22, "financial_imperative": 20}),
        ("iq", {"customer_journey": 7}),
        ("readiness", {"customer_journey": 18, "brand_magnetism": 15}),
    ]
    # Each change names what it set, moved or removed, compared with the same scale.
    assert [h["changed"] for h in history] == [
        ["customer_journey", "brand_magnetism", "financial_imperative"],
        ["customer_journey"],
        ["customer_journey", "brand_magnetism"],
    ]
    assert {h["set_by_name"] for h in history} == {"Olive Owner"}


def test_saving_the_same_targets_writes_nothing(client: TestClient, db: Session) -> None:
    owner, org = member(MembershipRole.OWNER)
    as_user(client, owner, org)
    assert _put(client, "iq", {}).status_code == 200  # nothing set, nothing to write
    _put(client, "iq", {"customer_journey": 8})
    again = _put(client, "iq", {"customer_journey": 8, "brand_magnetism": None})
    assert again.status_code == 200, again.text
    assert len(list(db.scalars(select(DimensionTargets)))) == 1
    events = list(
        db.scalars(select(AuditEvent).where(AuditEvent.action == AuditAction.TARGETS_CHANGED))
    )
    assert len(events) == 1

    # Clearing every target is a change, and is kept too.
    assert _put(client, "iq", {}).status_code == 200
    assert set(_by_key(client.get(BASE).json()["iq"]).values()) == {None}
    assert len(list(db.scalars(select(DimensionTargets)))) == 2


@pytest.mark.parametrize(
    ("scale", "value", "ok"),
    [
        ("readiness", 4, False),
        ("readiness", 5, True),
        ("readiness", 25, True),
        ("readiness", 26, False),
        ("iq", 0, False),
        ("iq", 1, True),
        ("iq", 10, True),
        ("iq", 11, False),
    ],
)
def test_a_target_must_be_a_possible_dimension_score(
    client: TestClient, db: Session, scale: str, value: int, ok: bool
) -> None:
    owner, org = member(MembershipRole.OWNER)
    as_user(client, owner, org)
    response = _put(client, scale, {"customer_journey": value})
    if ok:
        assert response.status_code == 200, response.text
        assert _by_key(response.json()[scale])["customer_journey"] == value
    else:
        assert response.status_code == 422, response.text
        assert response.json()["error"]["code"] == "invalid_targets"
        assert list(db.scalars(select(DimensionTargets))) == []


@pytest.mark.parametrize("bad", [7.5, "7", True, [7], {"value": 7}])
def test_a_target_must_be_a_whole_number(client: TestClient, bad: Any) -> None:
    owner, org = member(MembershipRole.OWNER)
    as_user(client, owner, org)
    assert _put(client, "iq", {"customer_journey": bad}).status_code == 422


def test_unknown_dimensions_scales_and_fields_are_refused(client: TestClient) -> None:
    owner, org = member(MembershipRole.OWNER)
    as_user(client, owner, org)
    unknown = _put(client, "iq", {"not_a_dimension": 5})
    assert unknown.status_code == 422
    assert unknown.json()["error"]["code"] == "invalid_targets"
    assert _put(client, "overall", {"customer_journey": 5}).status_code == 422
    extra = client.put(f"{BASE}/iq", json={"targets": {}, "total": 250}, headers=csrf(client))
    assert extra.status_code == 422
    too_many = _put(client, "iq", {f"k{i}": 5 for i in range(21)})
    assert too_many.status_code == 422


def test_owners_and_admins_set_targets_everyone_else_reads(client: TestClient) -> None:
    owner, org = member(MembershipRole.OWNER)
    admin, _ = member(MembershipRole.ADMIN, org)
    as_user(client, admin, org)
    assert _put(client, "iq", {"customer_journey": 9}).status_code == 200

    for role in (MembershipRole.MEMBER, MembershipRole.COMMITTEE, MembershipRole.INVESTOR):
        person, _ = member(role, org)
        as_user(client, person, org)
        body = client.get(BASE).json()
        assert body["can_change"] is False, role
        assert _by_key(body["iq"])["customer_journey"] == 9, role
        refused = _put(client, "iq", {"customer_journey": 1})
        assert refused.status_code == 403, role
        assert refused.json()["error"]["code"] == "forbidden"

    consultant = verified_user()
    ConsultantGrantFactory.create(
        organisation=org,
        consultant_email=consultant.email,
        consultant_user_id=consultant.id,
        accepted_at=datetime.now(UTC),
    )
    as_user(client, consultant, org)
    assert _by_key(client.get(BASE).json()["iq"])["customer_journey"] == 9
    assert client.get(BASE).json()["can_change"] is False
    assert _put(client, "iq", {"customer_journey": 1}).status_code == 403

    as_user(client, owner, org)
    assert _by_key(client.get(BASE).json()["iq"])["customer_journey"] == 9  # nothing changed


def test_another_organisation_never_sees_or_changes_them(client: TestClient) -> None:
    owner, org = member(MembershipRole.OWNER)
    as_user(client, owner, org)
    _put(client, "readiness", {"customer_journey": 21})

    outsider, other = member(MembershipRole.OWNER)
    as_user(client, outsider, other)
    assert set(_by_key(client.get(BASE).json()["readiness"]).values()) == {None}
    assert client.get(f"{BASE}/history").json() == []
    _put(client, "readiness", {"customer_journey": 6})

    as_user(client, owner, org)
    assert _by_key(client.get(BASE).json()["readiness"])["customer_journey"] == 21
    assert len(client.get(f"{BASE}/history").json()) == 1


def test_the_change_is_logged_without_any_value(client: TestClient, db: Session) -> None:
    owner, org = member(MembershipRole.OWNER)
    as_user(client, owner, org)
    _put(client, "readiness", {"customer_journey": 21, "brand_magnetism": 19})
    event = db.scalar(select(AuditEvent).where(AuditEvent.action == AuditAction.TARGETS_CHANGED))
    assert event is not None
    assert event.organisation_id == org.id
    assert event.actor_user_id == owner.id
    assert event.details == {
        "scale": "readiness",
        "changed": ["customer_journey", "brand_magnetism"],
        "question_set_version": QUESTION_SET.version,
    }
    assert "21" not in str(event.details)


def test_an_archived_organisation_keeps_its_targets_read_only(
    client: TestClient, db: Session
) -> None:
    owner, org = member(MembershipRole.OWNER)
    as_user(client, owner, org)
    _put(client, "iq", {"customer_journey": 9})
    org.status = OrganisationStatus.ARCHIVED
    db.commit()
    body = client.get(BASE).json()
    assert _by_key(body["iq"])["customer_journey"] == 9
    assert body["can_change"] is False
    refused = _put(client, "iq", {"customer_journey": 2})
    assert refused.status_code == 403
    assert refused.json()["error"]["code"] == "organisation_archived"


def test_targets_set_on_another_question_set_version_do_not_apply(
    client: TestClient, db: Session
) -> None:
    owner, org = member(MembershipRole.OWNER)
    as_user(client, owner, org)
    _put(client, "iq", {"customer_journey": 9})
    row = db.scalar(select(DimensionTargets))
    assert row is not None
    row.question_set_version = QUESTION_SET.version + 1
    db.commit()
    assert set(_by_key(client.get(BASE).json()["iq"]).values()) == {None}


def test_writes_need_a_session_and_the_csrf_header(client: TestClient) -> None:
    owner, org = member(MembershipRole.OWNER)
    as_user(client, owner, org)
    no_csrf = client.put(f"{BASE}/iq", json={"targets": {"customer_journey": 9}})
    assert no_csrf.status_code == 403
    assert no_csrf.json()["error"]["code"] == "csrf_failed"
    client.cookies.clear()
    assert client.get(BASE).status_code == 401

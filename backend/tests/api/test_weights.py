"""Dimension importance over HTTP (spec 3.4 and 7; Amy Q2; PROVISIONAL Q22, Q23).

Weights never change a score or the IQ. They only order tied priorities of an idea, and the
weights in force at confirmation are kept with the assessment.
"""

from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any

import httpx2
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import AuditEvent, DimensionWeights, IqAssessment, Organisation, User
from app.models.enums import MembershipRole
from app.scoring.question_set import QUESTION_SET
from app.services.audit import AuditAction
from tests.ai.support import RecordedAiClient, fixture, recorded_replies
from tests.api.helpers import csrf, member, signed_in
from tests.factories import ConsultantGrantFactory, verified_user

UseAi = Callable[..., RecordedAiClient]

BASE = "/api/v1/weights"
GOLDEN = fixture("propose_iq_scores", "typical")
KEYS = list(QUESTION_SET.dimension_keys)


def _as(client: TestClient, user: User, org: Organisation) -> None:
    client.cookies.clear()
    signed_in(client, user, org)


def _weights(**changes: Any) -> dict[str, Any]:
    weights: dict[str, Any] = dict.fromkeys(KEYS, 1)
    weights.update(changes)
    return weights


def _put(client: TestClient, weights: dict[str, Any]) -> httpx2.Response:
    response: httpx2.Response = client.put(BASE, json={"weights": weights}, headers=csrf(client))
    return response


def _by_key(body: dict[str, Any]) -> dict[str, str]:
    return {w["key"]: w["weight"] for w in body["weights"]}


def test_every_dimension_counts_equally_until_someone_changes_it(client: TestClient) -> None:
    owner, org = member(MembershipRole.OWNER)
    _as(client, owner, org)
    response = client.get(BASE)
    assert response.status_code == 200, response.text
    body = response.json()
    assert [w["key"] for w in body["weights"]] == KEYS  # book order
    assert set(_by_key(body).values()) == {"1"}
    assert body["custom"] is False
    assert body["set_at"] is None
    assert body["set_by_name"] is None
    assert body["can_change"] is True
    assert body["limits"] == {"minimum": 0, "maximum": 1000, "max_decimal_places": 6}
    assert client.get(f"{BASE}/history").json() == []


def test_an_owner_sets_the_importance_and_the_change_is_kept(
    client: TestClient, db: Session
) -> None:
    owner, org = member(MembershipRole.OWNER, name="Olive Owner")
    _as(client, owner, org)

    response = _put(client, _weights(customer_journey="2.5", data_intelligence=3))
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["custom"] is True
    assert body["set_by_name"] == "Olive Owner"
    assert body["set_at"] is not None
    assert _by_key(body)["customer_journey"] == "2.5"
    assert _by_key(body)["data_intelligence"] == "3"
    assert _by_key(body)["brand_magnetism"] == "1"

    history = client.get(f"{BASE}/history").json()
    assert len(history) == 1
    assert history[0]["custom"] is True
    assert history[0]["set_by_name"] == "Olive Owner"
    assert history[0]["weights"]["customer_journey"] == "2.5"

    event = db.scalars(
        select(AuditEvent).where(AuditEvent.action == AuditAction.WEIGHTS_CHANGED.value)
    ).one()
    assert event.organisation_id == org.id
    assert event.details == {"changed": ["customer_journey", "data_intelligence"], "custom": True}
    assert "2.5" not in str(event.details)  # names only, never values

    # The same weights again change nothing and leave no trace.
    again = _put(client, _weights(customer_journey="2.50", data_intelligence="3"))
    assert again.status_code == 200
    assert len(client.get(f"{BASE}/history").json()) == 1
    assert db.scalar(select(DimensionWeights).where(DimensionWeights.organisation_id == org.id))


def test_reset_puts_every_dimension_back_to_equal(client: TestClient) -> None:
    owner, org = member(MembershipRole.OWNER)
    _as(client, owner, org)
    assert _put(client, _weights(brand_magnetism=4)).json()["custom"] is True

    response = client.post(f"{BASE}/reset", headers=csrf(client))
    assert response.status_code == 200, response.text
    assert response.json()["custom"] is False
    assert set(_by_key(response.json()).values()) == {"1"}
    history = client.get(f"{BASE}/history").json()
    assert [h["custom"] for h in history] == [False, True]  # newest first

    # Resetting equal weights is a no-op.
    assert client.post(f"{BASE}/reset", headers=csrf(client)).status_code == 200
    assert len(client.get(f"{BASE}/history").json()) == 2


def test_the_engine_checks_the_values(client: TestClient) -> None:
    owner, org = member(MembershipRole.OWNER)
    _as(client, owner, org)
    cases: list[tuple[dict[str, Any], str]] = [
        (_weights(customer_journey=1001), "0 to 1000"),
        (_weights(customer_journey=-1), "0 to 1000"),
        (_weights(customer_journey="0.1234567"), "at most 6 decimal places"),
        (dict.fromkeys(KEYS, 0), "above zero"),
        (dict.fromkeys(KEYS[:-1], 1), "missing"),
        (_weights(made_up=1), "Unknown dimension"),
    ]
    for weights, message in cases:
        response = _put(client, weights)
        assert response.status_code == 422, (weights, response.text)
        assert response.json()["error"]["code"] == "invalid_weights"
        assert message in response.json()["error"]["message"]
    assert client.get(f"{BASE}/history").json() == []

    not_a_number = client.put(
        BASE, json={"weights": _weights(customer_journey="lots")}, headers=csrf(client)
    )
    assert not_a_number.status_code == 422


def test_only_owners_and_admins_change_the_importance(client: TestClient) -> None:
    owner, org = member(MembershipRole.OWNER)
    admin, _ = member(MembershipRole.ADMIN, org)
    mia, _ = member(MembershipRole.MEMBER, org)
    ivan, _ = member(MembershipRole.INVESTOR, org)

    _as(client, admin, org)
    assert _put(client, _weights(brand_magnetism=2)).status_code == 200

    for person in (mia, ivan):
        _as(client, person, org)
        seen = client.get(BASE)
        assert seen.status_code == 200
        assert seen.json()["custom"] is True
        assert seen.json()["can_change"] is False
        assert _put(client, _weights(brand_magnetism=3)).status_code == 403
        assert client.post(f"{BASE}/reset", headers=csrf(client)).status_code == 403
        assert client.get(f"{BASE}/history").status_code == 200

    _as(client, owner, org)
    assert _by_key(client.get(BASE).json())["brand_magnetism"] == "2"


def test_a_consultant_sees_the_importance_but_cannot_change_it(client: TestClient) -> None:
    _owner, org = member(MembershipRole.OWNER)
    amy = verified_user(email="amy@example.com")
    ConsultantGrantFactory.create(
        organisation=org,
        consultant_email=amy.email,
        consultant_user_id=amy.id,
        accepted_at=datetime.now(UTC),
    )
    _as(client, amy, org)
    seen = client.get(BASE)
    assert seen.status_code == 200
    assert seen.json()["can_change"] is False
    assert _put(client, _weights(brand_magnetism=2)).status_code == 403


def test_importance_stays_inside_its_organisation(client: TestClient) -> None:
    owner_a, org_a = member(MembershipRole.OWNER)
    owner_b, org_b = member(MembershipRole.OWNER)
    _as(client, owner_a, org_a)
    assert _put(client, _weights(brand_magnetism=2)).status_code == 200
    _as(client, owner_b, org_b)
    body = client.get(BASE).json()
    assert body["custom"] is False
    assert client.get(f"{BASE}/history").json() == []


def test_importance_orders_tied_priorities_and_never_the_iq(
    client: TestClient, use_ai: UseAi, db: Session
) -> None:
    """The recorded proposal has Channel Navigation and Operational Efficiency tied at 6
    (book order puts Channel Navigation first) and three dimensions tied at 7. Importance
    reorders the ties; the IQ, levels and category scores are exactly as before."""
    use_ai(*recorded_replies(GOLDEN), *recorded_replies(GOLDEN))
    owner, org = member(MembershipRole.OWNER)
    _as(client, owner, org)
    assert _put(client, _weights(operational_efficiency=3, service_excellence=2)).status_code == 200

    created = client.post(
        "/api/v1/ideas",
        json={**GOLDEN["idea"], "investment": "50000.00"},
        headers=csrf(client),
    )
    assert created.status_code == 201, created.text
    idea_id = created.json()["id"]
    proposal = client.post(f"/api/v1/ideas/{idea_id}/assessments", headers=csrf(client))
    assert proposal.status_code == 201, proposal.text
    assessment_id = proposal.json()["id"]
    assert proposal.json()["custom_weights"] is False  # nothing is confirmed yet

    confirmed = client.post(
        f"/api/v1/ideas/{idea_id}/assessments/{assessment_id}/confirm", headers=csrf(client)
    )
    assert confirmed.status_code == 200, confirmed.text
    body = confirmed.json()
    assert body["iq"] == "69.2"  # 83 / 120, unchanged by the weights
    assert body["custom_weights"] is True
    assert [(p["rank"], p["key"], p["score"]) for p in body["priorities"]] == [
        (1, "organizational_agility", 4),
        (2, "sustainable_future", 5),
        (3, "operational_efficiency", 6),  # before Channel Navigation: more important
        (4, "channel_navigation", 6),
        (5, "service_excellence", 7),  # before Brand Magnetism and Collaborative Synergy
    ]
    row = db.get(IqAssessment, assessment_id)
    assert row is not None
    assert row.weights_snapshot is not None
    assert row.weights_snapshot["operational_efficiency"] == "3"
    assert row.weights_snapshot["brand_magnetism"] == "1"

    # Changing the importance afterwards leaves the confirmed assessment as it was.
    assert client.post(f"{BASE}/reset", headers=csrf(client)).status_code == 200
    after = client.get(f"/api/v1/ideas/{idea_id}/assessments/{assessment_id}").json()
    assert after["priorities"] == body["priorities"]
    assert after["custom_weights"] is True

    # The same proposal confirmed under equal importance: every number the same, only the
    # order of the tied priorities differs (Q2: weights change no score).
    again = client.post(f"/api/v1/ideas/{idea_id}/assessments", headers=csrf(client)).json()
    equal = client.post(
        f"/api/v1/ideas/{idea_id}/assessments/{again['id']}/confirm", headers=csrf(client)
    ).json()
    assert equal["custom_weights"] is False
    assert equal["iq"] == body["iq"] == "69.2"
    assert equal["categories"] == body["categories"]
    assert [c["score"] for c in body["categories"]] == ["74.0", "50.0", "72.0"]
    assert [(d["key"], d["level"]["name"]) for d in equal["dimensions"]] == [
        (d["key"], d["level"]["name"]) for d in body["dimensions"]
    ]
    assert [(p["key"], p["score"]) for p in equal["priorities"]] == [
        ("organizational_agility", 4),
        ("sustainable_future", 5),
        ("channel_navigation", 6),
        ("operational_efficiency", 6),
        ("brand_magnetism", 7),
    ]


def test_equal_importance_keeps_book_order(client: TestClient, use_ai: UseAi) -> None:
    use_ai(*recorded_replies(GOLDEN))
    owner, org = member(MembershipRole.OWNER)
    _as(client, owner, org)
    created = client.post(
        "/api/v1/ideas", json={**GOLDEN["idea"], "investment": "50000.00"}, headers=csrf(client)
    )
    idea_id = created.json()["id"]
    assessment_id = client.post(
        f"/api/v1/ideas/{idea_id}/assessments", headers=csrf(client)
    ).json()["id"]
    body = client.post(
        f"/api/v1/ideas/{idea_id}/assessments/{assessment_id}/confirm", headers=csrf(client)
    ).json()
    assert body["custom_weights"] is False
    assert [p["key"] for p in body["priorities"]] == [
        "organizational_agility",
        "sustainable_future",
        "channel_navigation",
        "operational_efficiency",
        "brand_magnetism",
    ]


def test_importance_needs_a_session(client: TestClient) -> None:
    assert client.get(BASE).status_code == 401

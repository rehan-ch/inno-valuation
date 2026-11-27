"""PDF reports over HTTP (Phase 7): asking, drawing, downloading, the email, who may do what,
and that every number in the PDF is the number the app shows for the same result."""

import io
import re
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from fastapi.testclient import TestClient
from pypdf import PdfReader
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.storage import get_storage
from app.emails.backends import MemoryEmailBackend
from app.jobs.tasks import reports as report_tasks
from app.models import AuditEvent, Membership, Organisation, Report, User
from app.models.enums import MembershipRole, OrganisationStatus, ReportStatus
from app.scoring.question_set import QUESTION_SET
from app.services import reports
from tests.ai.support import RecordedAiClient, fixture, recorded_replies
from tests.api.flows import (
    IDEAS,
    READINESS,
    add_idea,
    answers_190,
    as_user,
    confirmed_idea,
    finish_readiness,
    propose,
)
from tests.api.helpers import csrf, member
from tests.factories import ConsultantGrantFactory, verified_user

UseAi = Callable[..., RecordedAiClient]

ADVICE_PARTS = ("interpret_results", "bridge_gaps", "recommendations", "consultation_nudge")


def _readiness(client: TestClient) -> tuple[User, Organisation, str, str]:
    """An owner with a final readiness result of 190 and a target on Customer Journey.
    Returns the owner, the organisation, the result's id and its reports URL."""
    owner, org = member(MembershipRole.OWNER)
    as_user(client, owner, org)
    assessment_id = finish_readiness(client, answers_190())
    saved = client.put(
        "/api/v1/targets/readiness",
        json={"targets": {"customer_journey": 23}},
        headers=csrf(client),
    )
    assert saved.status_code == 200, saved.text
    return owner, org, assessment_id, f"{READINESS}/assessments/{assessment_id}/reports"


def _make(client: TestClient, url: str) -> dict[str, Any]:
    response = client.post(url, headers=csrf(client))
    assert response.status_code == 200, response.text
    body: dict[str, Any] = response.json()
    return body


def _list(client: TestClient, url: str) -> dict[str, Any]:
    response = client.get(url)
    assert response.status_code == 200, response.text
    body: dict[str, Any] = response.json()
    return body


def _download(client: TestClient, url: str, report_id: str) -> bytes:
    response = client.get(f"{url}/{report_id}/file")
    assert response.status_code == 200, response.text
    assert response.headers["content-type"] == "application/pdf"
    return response.content


def _text(pdf: bytes) -> str:
    """The PDF's words, with every run of white space as one space."""
    reader = PdfReader(io.BytesIO(pdf))
    return " ".join(" ".join(page.extract_text() or "" for page in reader.pages).split())


def _count(db: Session) -> int:
    return int(db.scalar(select(func.count()).select_from(Report)) or 0)


def test_a_readiness_report_from_asking_to_download(
    client: TestClient, db: Session, outbox: MemoryEmailBackend
) -> None:
    owner, _, assessment_id, url = _readiness(client)
    empty = _list(client, url)
    assert empty["reports"] == []
    assert empty["can_request"] is True
    assert empty["subject"] == "readiness_result"

    body = _make(client, url)
    [report] = body["reports"]
    assert report["status"] == "ready"  # Celery runs eagerly in tests
    assert report["version"] == 1
    assert report["requested_by_name"] == owner.name
    assert report["page_count"] >= 1
    assert report["file_size"] > 0

    response = client.get(f"{url}/{report['id']}/file")
    assert response.status_code == 200
    assert response.content.startswith(b"%PDF-")
    disposition = response.headers["content-disposition"]
    assert re.fullmatch(
        r'attachment; filename="innovaluation-readiness-report-\d{4}-\d{2}-\d{2}-v1\.pdf"',
        disposition,
    )
    assert response.headers["cache-control"] == "private, no-store"
    assert len(response.content) == report["file_size"]

    # The email says it is ready and where to get it, and nothing about the result.
    [email] = [m for m in outbox.outbox if m.subject == "Your InnoValuation report is ready"]
    assert email.to == owner.email
    assert email.link.endswith(f"/readiness/{assessment_id}/result")
    assert "190" not in email.text
    assert "Building Blocks" not in email.text

    [event] = db.scalars(select(AuditEvent).where(AuditEvent.action == "report.requested"))
    assert event.details == {
        "subject": "readiness_result",
        "assessment_id": assessment_id,
        "question_set_version": 1,
        "version": 1,
    }


def test_every_number_in_the_readiness_pdf_is_the_number_the_app_shows(
    client: TestClient,
) -> None:
    _, _, assessment_id, url = _readiness(client)
    shown = _list(client, f"{READINESS}/assessments/{assessment_id}/result")
    report = _make(client, url)["reports"][0]
    text = _text(_download(client, url, report["id"]))

    assert f"{shown['total']} / {shown['total_maximum']}" in text
    assert shown["band"]["name"] in text
    assert shown["band"]["text"] in text
    for category in shown["categories"]:
        assert f"{category['score']} / {category['maximum']}" in text
    for segment in shown["compass"]["segments"]:
        assert f"{segment['name']}" in text
        assert f"{segment['score']} / {segment['maximum']}" in text
    target = next(s for s in shown["compass"]["segments"] if s["target"] is not None)
    assert f"{target['gap']} below target" in text
    for priority in shown["priorities"]:
        # The method's next steps, word for word.
        assert " ".join(priority["next_steps"].split()) in text
    for strength in shown["strengths"]:
        assert strength["name"] in text
    assert "question set version 1" in text
    assert "Proposed by AI" not in text  # without a key the app shows no advice


def test_every_number_in_the_idea_pdf_is_the_number_the_app_shows(
    client: TestClient, use_ai: UseAi
) -> None:
    owner, org = member(MembershipRole.OWNER)
    as_user(client, owner, org)
    idea_id, assessment_id = confirmed_idea(client, use_ai)
    base = f"{IDEAS}/{idea_id}/assessments/{assessment_id}"
    shown = _list(client, base)
    report = _make(client, f"{base}/reports")["reports"][0]
    assert report["status"] == "ready"
    text = _text(_download(client, f"{base}/reports", report["id"]))

    # The golden flow: IQ 70.0, Value for Money 714.29 for 50,000.
    assert shown["iq"] == "70.0"
    assert f"{shown['iq']} / {shown['iq_maximum']}" in text
    assert "USD 714.29" in text
    assert "USD 50,000.00" in text
    for category in shown["categories"]:
        assert f"{category['score']} / {category['maximum']}" in text
    for segment in shown["compass"]["segments"]:
        assert f"{segment['score']} / {segment['maximum']}" in text
        assert segment["level"]["name"] in text
    for priority in shown["priorities"]:
        assert " ".join(priority["next_steps"].split()) in text
    assert "innovation quotient report" in text.lower()
    assert "readiness" not in text.lower()  # the two scores are never mixed


def test_the_ai_advice_goes_in_only_where_the_app_shows_it(
    client: TestClient, db: Session, use_ai: UseAi
) -> None:
    _, _, assessment_id, url = _readiness(client)
    advice_url = f"{READINESS}/assessments/{assessment_id}/advice"
    use_ai(*[r for part in ADVICE_PARTS for r in recorded_replies(fixture(part, "typical"))])
    asked = client.post(advice_url, json={}, headers=csrf(client))
    assert asked.status_code == 200, asked.text
    advice = asked.json()

    report = _make(client, url)["reports"][0]
    stored = db.get(Report, report["id"])
    assert stored is not None
    assert set(stored.snapshot["advice"]) == {
        "interpretation",
        "gap_actions",
        "recommendations",
        "consultation",
    }
    assert all("usage" not in part for part in stored.snapshot["advice"].values())
    text = _text(_download(client, url, report["id"]))
    assert "Proposed by AI" in text
    assert " ".join(advice["interpretation"]["summary"][0].split()) in text
    for item in advice["recommendations"]["items"]:
        assert " ".join(item["fixed_text"].split()) in text


def test_sample_advice_from_the_stand_in_stays_out(client: TestClient, db: Session) -> None:
    _, _, assessment_id, url = _readiness(client)
    asked = client.post(
        f"{READINESS}/assessments/{assessment_id}/advice", json={}, headers=csrf(client)
    )
    assert asked.status_code == 200  # the offline stand-in answers with marked samples
    report = _make(client, url)["reports"][0]
    stored = db.get(Report, report["id"])
    assert stored is not None
    assert stored.snapshot["advice"] is None


def test_asking_twice_gives_one_report_until_something_changes(
    client: TestClient, db: Session
) -> None:
    _, _, _, url = _readiness(client)
    first = _make(client, url)["reports"]
    again = _make(client, url)["reports"]
    assert [r["id"] for r in again] == [first[0]["id"]]
    assert _count(db) == 1

    changed = client.put(
        "/api/v1/targets/readiness",
        json={"targets": {"customer_journey": 24}},
        headers=csrf(client),
    )
    assert changed.status_code == 200
    newer = _make(client, url)["reports"]
    assert [r["version"] for r in newer] == [2, 1]
    # Each version keeps what it showed: the first still has the old target.
    old, new = (db.get(Report, r["id"]) for r in reversed(newer))
    assert old is not None
    assert new is not None
    targets = [
        next(s["target"] for s in r.snapshot["result"]["compass"]["segments"] if s["target"])
        for r in (old, new)
    ]
    assert targets == [23, 24]
    for report in newer:
        assert _download(client, url, report["id"]).startswith(b"%PDF-")


def test_no_report_before_the_result_is_final_or_confirmed(
    client: TestClient, db: Session, use_ai: UseAi
) -> None:
    owner, org = member(MembershipRole.OWNER)
    as_user(client, owner, org)
    started = client.post(f"{READINESS}/assessments", headers=csrf(client)).json()["id"]
    url = f"{READINESS}/assessments/{started}/reports"
    assert client.get(url).status_code == 404
    assert client.post(url, headers=csrf(client)).status_code == 404

    idea_id = add_idea(client)
    assessment_id = propose(client, use_ai, idea_id)
    url = f"{IDEAS}/{idea_id}/assessments/{assessment_id}/reports"
    assert client.get(url).status_code == 404
    assert client.post(url, headers=csrf(client)).status_code == 404
    assert _count(db) == 0


@pytest.mark.parametrize(
    ("role", "may_make"),
    [
        (MembershipRole.ADMIN, True),
        (MembershipRole.MEMBER, True),
        (MembershipRole.COMMITTEE, True),
        (MembershipRole.INVESTOR, False),
    ],
)
def test_who_may_make_and_download(
    client: TestClient, db: Session, role: MembershipRole, may_make: bool
) -> None:
    _, org, _, url = _readiness(client)
    made = _make(client, url)["reports"][0]
    person, _ = member(role, org)
    as_user(client, person, org)
    listed = _list(client, url)
    assert listed["can_request"] is may_make
    assert _download(client, url, made["id"]).startswith(b"%PDF-")
    # Nothing has changed, so a permitted ask returns the same report.
    assert client.post(url, headers=csrf(client)).status_code == (200 if may_make else 403)
    assert _count(db) == 1


def test_a_consultant_downloads_and_never_makes(client: TestClient, db: Session) -> None:
    _, org, _, url = _readiness(client)
    made = _make(client, url)["reports"][0]
    consultant = verified_user()
    ConsultantGrantFactory.create(
        organisation=org,
        consultant_email=consultant.email,
        consultant_user_id=consultant.id,
        accepted_at=datetime.now(UTC),
    )
    as_user(client, consultant, org)
    assert _list(client, url)["can_request"] is False
    assert _download(client, url, made["id"]).startswith(b"%PDF-")
    assert client.post(url, headers=csrf(client)).status_code == 403
    assert _count(db) == 1


def test_another_organisation_sees_and_downloads_nothing(
    client: TestClient, db: Session, use_ai: UseAi
) -> None:
    _, _, _, url = _readiness(client)
    made = _make(client, url)["reports"][0]
    idea_owner, idea_org = member(MembershipRole.OWNER)
    as_user(client, idea_owner, idea_org)
    idea_id, assessment_id = confirmed_idea(client, use_ai)
    idea_url = f"{IDEAS}/{idea_id}/assessments/{assessment_id}/reports"
    idea_report = _make(client, idea_url)["reports"][0]

    # A report id under another result of one's own organisation is not found either.
    assert client.get(f"{idea_url}/{made['id']}/file").status_code == 404

    outsider, other_org = member(MembershipRole.OWNER)
    as_user(client, outsider, other_org)
    for hidden, report_id in ((url, made["id"]), (idea_url, idea_report["id"])):
        assert client.get(hidden).status_code == 404
        assert client.post(hidden, headers=csrf(client)).status_code == 404
        assert client.get(f"{hidden}/{report_id}/file").status_code == 404
    assert _count(db) == 2


def test_an_archived_organisation_keeps_its_reports_but_makes_no_new_one(
    client: TestClient, db: Session
) -> None:
    _, org, _, url = _readiness(client)
    made = _make(client, url)["reports"][0]
    org.status = OrganisationStatus.ARCHIVED
    db.flush()
    assert _list(client, url)["can_request"] is False
    assert _download(client, url, made["id"]).startswith(b"%PDF-")
    refused = client.post(url, headers=csrf(client))
    assert refused.status_code == 403
    assert refused.json()["error"]["code"] == "organisation_archived"


def test_a_report_that_cannot_be_drawn_fails_and_can_be_made_again(
    client: TestClient, db: Session, monkeypatch: pytest.MonkeyPatch, outbox: MemoryEmailBackend
) -> None:
    def broken(snapshot: dict[str, Any]) -> Any:
        raise ValueError("layout")

    _, _, _, url = _readiness(client)
    monkeypatch.setattr(report_tasks, "render_pdf", broken)
    failed = _make(client, url)["reports"][0]
    assert failed["status"] == "failed"
    refused = client.get(f"{url}/{failed['id']}/file")
    assert refused.status_code == 409
    assert refused.json()["error"]["code"] == "report_not_ready"
    stored = db.get(Report, failed["id"])
    assert stored is not None
    assert stored.error == "The PDF could not be drawn (ValueError)."
    assert not [m for m in outbox.outbox if "report is ready" in m.subject]

    monkeypatch.undo()
    again = _make(client, url)["reports"]
    assert [(r["version"], r["status"]) for r in again] == [(2, "ready"), (1, "failed")]


def test_a_report_left_pending_by_a_lost_worker_is_failed_when_read(
    client: TestClient, db: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    _, _, _, url = _readiness(client)
    monkeypatch.setattr(report_tasks.render_report, "delay", lambda report_id: None)
    pending = _make(client, url)["reports"][0]
    assert pending["status"] == "queued"
    assert _make(client, url)["reports"][0]["id"] == pending["id"]  # still on its way

    stored = db.get(Report, pending["id"])
    assert stored is not None
    stored.created_at = datetime.now(UTC) - reports.STALE_AFTER - timedelta(seconds=1)
    db.flush()
    assert _list(client, url)["reports"][0]["status"] == "failed"
    # A late worker leaves the failed report alone.
    assert report_tasks.render_report(str(stored.id)) == report_tasks.SKIPPED


def test_a_missing_or_changed_file_is_never_served(client: TestClient, db: Session) -> None:
    _, _, _, url = _readiness(client)
    made = _make(client, url)["reports"][0]
    stored = db.get(Report, made["id"])
    assert stored is not None
    assert stored.file_key is not None
    get_storage().put(stored.file_key, b"%PDF-1.7 something else")
    changed = client.get(f"{url}/{made['id']}/file")
    assert changed.status_code == 410
    assert changed.json()["error"]["code"] == "report_file_missing"
    get_storage().delete(stored.file_key)
    assert client.get(f"{url}/{made['id']}/file").status_code == 410


def test_the_daily_limit(client: TestClient, db: Session, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(reports, "DAILY_LIMIT", 1)
    _, _, _, url = _readiness(client)
    _make(client, url)
    client.put(
        "/api/v1/targets/readiness",
        json={"targets": {"customer_journey": 24}},
        headers=csrf(client),
    )
    refused = client.post(url, headers=csrf(client))
    assert refused.status_code == 429
    assert _count(db) == 1


def test_making_a_report_needs_the_csrf_header(client: TestClient, db: Session) -> None:
    _, _, _, url = _readiness(client)
    assert client.post(url).status_code == 403
    assert _count(db) == 0


def test_the_ready_email_goes_only_to_someone_who_can_still_see_the_result(
    client: TestClient, db: Session, outbox: MemoryEmailBackend, monkeypatch: pytest.MonkeyPatch
) -> None:
    owner, org, _, url = _readiness(client)
    monkeypatch.setattr(report_tasks.send_report_ready, "delay", lambda report_id: None)
    made = _make(client, url)["reports"][0]
    membership = db.scalars(
        select(Membership).where(
            Membership.user_id == owner.id, Membership.organisation_id == org.id
        )
    ).one()
    db.delete(membership)
    db.flush()
    assert report_tasks.send_report_ready(made["id"]) == report_tasks.SKIPPED
    assert not outbox.outbox or all("report is ready" not in m.subject for m in outbox.outbox)


def test_drawing_is_idempotent(client: TestClient, db: Session) -> None:
    _, _, _, url = _readiness(client)
    made = _make(client, url)["reports"][0]
    assert report_tasks.render_report(made["id"]) == report_tasks.SKIPPED
    stored = db.get(Report, made["id"])
    assert stored is not None
    assert stored.status is ReportStatus.READY


def test_the_activity_log_says_a_report_was_made(client: TestClient) -> None:
    _, _, _, url = _readiness(client)
    _make(client, url)
    events = [
        e for e in client.get("/api/v1/audit").json()["events"] if e["action"] == "report.requested"
    ]
    assert [(e["action_label"], e["detail"]) for e in events] == [
        ("PDF report made", "For a readiness result, version 1.")
    ]


def test_the_report_names_every_dimension_in_book_order(client: TestClient) -> None:
    _, _, _, url = _readiness(client)
    made = _make(client, url)["reports"][0]
    text = _text(_download(client, url, made["id"]))
    places = [text.find(d.name) for d in QUESTION_SET.dimensions]
    assert all(place >= 0 for place in places)
    assert places == sorted(places)

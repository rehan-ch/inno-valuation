"""Team changes under real concurrency: separate sessions on separate connections.

The ``db`` fixture shares one session, so it cannot show races. These tests commit to the
test database and remove everything they created afterwards.
"""

import threading
import uuid
from collections.abc import Callable, Iterator
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import Engine, delete, select, update
from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.core.permissions import OrgContext, OrgRole
from app.core.security import hash_token, invitation_token_value
from app.models import AuditEvent, Invitation, Membership, Organisation, User
from app.models.enums import MembershipRole
from app.services import invitations, members


@dataclass(frozen=True)
class World:
    org_id: uuid.UUID
    admin_id: uuid.UUID
    invitee_id: uuid.UUID
    invitation_id: uuid.UUID
    token: str


@pytest.fixture
def world(db_engine: Engine) -> Iterator[World]:
    suffix = uuid.uuid4().hex[:10]
    now = datetime.now(UTC)
    with Session(db_engine) as session:
        org = Organisation(name=f"Race {suffix}")
        admin = User(email=f"admin-{suffix}@example.com", name="Admin", password_hash="x")
        invitee = User(
            email=f"invitee-{suffix}@example.com",
            name="Invitee",
            password_hash="x",
            email_verified_at=now,
        )
        session.add_all([org, admin, invitee])
        session.flush()
        session.add(Membership(organisation_id=org.id, user_id=admin.id, role=MembershipRole.ADMIN))
        invitation = Invitation(
            organisation_id=org.id,
            email=invitee.email,
            role=MembershipRole.MEMBER,
            invited_by_user_id=admin.id,
            expires_at=now + timedelta(days=7),
        )
        invitation.id = uuid.uuid4()
        token = invitation_token_value(invitation.id)
        invitation.token_hash = hash_token(token)
        session.add(invitation)
        session.commit()
        built = World(org.id, admin.id, invitee.id, invitation.id, token)
    try:
        yield built
    finally:
        with Session(db_engine) as session:
            session.execute(delete(AuditEvent).where(AuditEvent.organisation_id == built.org_id))
            session.execute(delete(Organisation).where(Organisation.id == built.org_id))
            session.execute(delete(User).where(User.id.in_([built.admin_id, built.invitee_id])))
            session.commit()


def _run_together(*actions: Callable[[], object]) -> list[object]:
    """Run each action in its own thread, released at the same moment. Returns each
    result, or the exception it raised."""
    results: list[object] = [None] * len(actions)
    start = threading.Barrier(len(actions))

    def run(index: int) -> None:
        start.wait()
        try:
            results[index] = actions[index]()
        except Exception as error:
            results[index] = error

    threads = [threading.Thread(target=run, args=(i,)) for i in range(len(actions))]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=30)
    return results


def _code(result: object) -> str | None:
    return result.code if isinstance(result, AppError) else None


@pytest.mark.parametrize("attempt", range(5))
def test_accept_and_cancel_never_both_succeed(
    db_engine: Engine, world: World, attempt: int
) -> None:
    del attempt  # repeated to give the race several chances

    def accept() -> object:
        with Session(db_engine) as session:
            user = session.get(User, world.invitee_id)
            assert user is not None
            return invitations.accept(session, user, token=world.token)

    def cancel() -> object:
        with Session(db_engine) as session:
            org = session.get(Organisation, world.org_id)
            admin = session.get(User, world.admin_id)
            assert org is not None
            assert admin is not None
            ctx = OrgContext(organisation=org, user=admin, role=OrgRole.ADMIN)
            invitations.revoke(org, session, ctx=ctx, invitation_id=world.invitation_id)
            return "cancelled"

    accepted, cancelled = _run_together(accept, cancel)
    # No deadlock or database error: each side either won or was refused cleanly.
    assert isinstance(accepted, Organisation) or _code(accepted) == "invalid_invitation"
    assert cancelled == "cancelled" or _code(cancelled) == "not_found"

    with Session(db_engine) as session:
        invitation = session.get(Invitation, world.invitation_id)
        assert invitation is not None
        joined = session.scalar(
            select(Membership).where(
                Membership.organisation_id == world.org_id,
                Membership.user_id == world.invitee_id,
            )
        )
    if isinstance(accepted, Organisation):
        assert cancelled != "cancelled"
        assert invitation.accepted_at is not None
        assert invitation.revoked_at is None
        assert joined is not None
    else:
        assert cancelled == "cancelled"
        assert invitation.revoked_at is not None
        assert joined is None

    # Reset for the next repetition.
    with Session(db_engine) as session:
        session.execute(
            delete(Membership).where(
                Membership.organisation_id == world.org_id,
                Membership.user_id == world.invitee_id,
            )
        )
        session.execute(
            update(Invitation)
            .where(Invitation.id == world.invitation_id)
            .values(accepted_at=None, revoked_at=None)
        )
        session.commit()


def test_role_is_re_read_even_when_the_session_holds_it(db_engine: Engine, world: World) -> None:
    """A request that loaded the actor's membership before another request demoted them
    must not act on the old role."""
    with Session(db_engine) as session:
        org = session.get(Organisation, world.org_id)
        admin = session.get(User, world.admin_id)
        assert org is not None
        assert admin is not None
        held = members.find_membership(org, session, admin.id)  # kept alive on purpose
        assert held is not None
        assert held.role is MembershipRole.ADMIN

        with Session(db_engine) as other:
            other.execute(
                update(Membership)
                .where(Membership.id == held.id)
                .values(role=MembershipRole.MEMBER)
            )
            other.commit()

        ctx = OrgContext(organisation=org, user=admin, role=OrgRole.ADMIN)
        with pytest.raises(AppError) as raised:
            members.actor_role(org, session, ctx)
        assert raised.value.code == "forbidden"
        assert str(held.role) == "member"  # the held object was refreshed too

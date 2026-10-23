"""factory-boy factories. One factory per model, all subclassing ``BaseFactory``.

The ``db`` fixture binds the per-test session with ``bind_session``, so factories write
inside the test transaction.

Use ``SomeFactory.create(...)`` (typed: it returns the model) rather than ``SomeFactory()``,
which type checkers read as constructing the factory itself.
"""

import hashlib
import secrets
from datetime import UTC, datetime, timedelta
from functools import cache
from typing import Any, cast

from factory.alchemy import SQLAlchemyModelFactory
from factory.declarations import LazyAttribute, LazyFunction, Sequence, SubFactory
from sqlalchemy.orm import Session

from app.core.security import hash_password, throttle_key
from app.models import (
    AuditEvent,
    ConsultantGrant,
    Invitation,
    Membership,
    Organisation,
    ReadinessAssessment,
    ReadinessConsensus,
    ReadinessResponse,
    ReadinessResult,
    SignInThrottle,
    User,
    UserToken,
)
from app.models.enums import MembershipRole, UserTokenPurpose

_session: Session | None = None


def bind_session(session: Session | None) -> None:
    # Module-level binding is how factory-boy factories find the per-test session.
    global _session  # noqa: PLW0603
    _session = session


def _get_session() -> Session:
    if _session is None:
        raise RuntimeError("Factories need the `db` fixture (no session bound).")
    return _session


def fake_token_hash() -> str:
    """A SHA-256 hex digest of a random token, the form tokens are stored in."""
    return hashlib.sha256(secrets.token_bytes(32)).hexdigest()


# The password every ``verified_user`` signs in with.
TEST_PASSWORD = "correct horse battery"


@cache
def password_hash_for_tests() -> str:
    """One argon2 hash of ``TEST_PASSWORD``, computed once per run (hashing is slow on purpose)."""
    return hash_password(TEST_PASSWORD)


def _in_days(days: int) -> datetime:
    return datetime.now(UTC) + timedelta(days=days)


class BaseFactory[M](SQLAlchemyModelFactory):
    class Meta:
        abstract = True
        sqlalchemy_session_factory = _get_session
        sqlalchemy_session_persistence = "flush"

    @classmethod
    def create(cls, **kwargs: Any) -> M:
        return cast(M, super().create(**kwargs))


class UserFactory(BaseFactory[User]):
    class Meta:
        model = User

    email = Sequence(lambda n: f"user{n}@example.com")
    name = Sequence(lambda n: f"User {n}")
    password_hash = "$argon2id$not-a-real-hash"


def verified_user(**kwargs: Any) -> User:
    """An active user with a verified email who signs in with ``TEST_PASSWORD``."""
    kwargs.setdefault("password_hash", password_hash_for_tests())
    kwargs.setdefault("email_verified_at", datetime.now(UTC))
    return UserFactory.create(**kwargs)


class OrganisationFactory(BaseFactory[Organisation]):
    class Meta:
        model = Organisation

    name = Sequence(lambda n: f"Organisation {n}")


class MembershipFactory(BaseFactory[Membership]):
    class Meta:
        model = Membership

    organisation = SubFactory(OrganisationFactory)
    user = SubFactory(UserFactory)
    role = MembershipRole.MEMBER


class InvitationFactory(BaseFactory[Invitation]):
    class Meta:
        model = Invitation

    organisation = SubFactory(OrganisationFactory)
    email = Sequence(lambda n: f"invitee{n}@example.com")
    role = MembershipRole.MEMBER
    token_hash = LazyFunction(fake_token_hash)
    expires_at = LazyFunction(lambda: _in_days(7))


class UserTokenFactory(BaseFactory[UserToken]):
    class Meta:
        model = UserToken

    user = SubFactory(UserFactory)
    purpose = UserTokenPurpose.VERIFY_EMAIL
    token_hash = LazyFunction(fake_token_hash)
    expires_at = LazyFunction(lambda: _in_days(1))


class ConsultantGrantFactory(BaseFactory[ConsultantGrant]):
    class Meta:
        model = ConsultantGrant

    organisation = SubFactory(OrganisationFactory)
    consultant_email = Sequence(lambda n: f"consultant{n}@example.com")
    expires_at = LazyFunction(lambda: _in_days(30))


class AuditEventFactory(BaseFactory[AuditEvent]):
    class Meta:
        model = AuditEvent

    action = "user.signed_in"


class SignInThrottleFactory(BaseFactory[SignInThrottle]):
    class Meta:
        model = SignInThrottle

    key_hash = Sequence(lambda n: throttle_key(f"throttled{n}@example.com"))
    attempt_count = 1
    window_started_at = LazyFunction(lambda: datetime.now(UTC))


class ReadinessAssessmentFactory(BaseFactory[ReadinessAssessment]):
    class Meta:
        model = ReadinessAssessment

    organisation = SubFactory(OrganisationFactory)
    question_set_version = 1


class ReadinessResponseFactory(BaseFactory[ReadinessResponse]):
    class Meta:
        model = ReadinessResponse

    assessment = SubFactory(ReadinessAssessmentFactory)
    organisation_id = LazyAttribute(lambda o: o.assessment.organisation_id)
    user = SubFactory(UserFactory)
    answers = LazyFunction(dict)


class ReadinessConsensusFactory(BaseFactory[ReadinessConsensus]):
    class Meta:
        model = ReadinessConsensus

    assessment = SubFactory(ReadinessAssessmentFactory)
    organisation_id = LazyAttribute(lambda o: o.assessment.organisation_id)
    answers = LazyFunction(dict)


class ReadinessResultFactory(BaseFactory[ReadinessResult]):
    class Meta:
        model = ReadinessResult

    assessment = SubFactory(ReadinessAssessmentFactory)
    organisation_id = LazyAttribute(lambda o: o.assessment.organisation_id)
    per_dimension = LazyFunction(dict)
    category_scores = LazyFunction(dict)
    total = 0
    participant_count = 1
    band_key = "foundation"
    priorities = LazyFunction(list)

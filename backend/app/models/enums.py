"""Enumerations stored in the database, plus the column type that stores them.

Values are stored as short strings with a CHECK constraint (not native Postgres enums),
so adding a value is a plain constraint change in a migration.
"""

from enum import StrEnum

from sqlalchemy import Enum


class MembershipRole(StrEnum):
    """A user's role inside one organisation.

    Platform staff are not a role here (``User.is_platform_admin``), and a consultant is
    never a member (``ConsultantGrant``).
    """

    OWNER = "owner"
    ADMIN = "admin"
    MEMBER = "member"
    COMMITTEE = "committee"
    # PROVISIONAL: see open-questions Q13. An investor is a role inside one company's
    # account (option a). Option b would need an investor workspace across organisations.
    INVESTOR = "investor"


class OrganisationStatus(StrEnum):
    ACTIVE = "active"
    ARCHIVED = "archived"


class UserTokenPurpose(StrEnum):
    VERIFY_EMAIL = "verify_email"
    RESET_PASSWORD = "reset_password"  # noqa: S105  (a purpose name, not a password)


class ConsultantGrantScope(StrEnum):
    READ_RESULTS = "read_results"


def enum_type(enum_cls: type[StrEnum], name: str, length: int = 20) -> Enum:
    """A VARCHAR column with a CHECK constraint named ``ck_<table>_<name>``.

    Stores the enum values (``"owner"``), not the member names (``"OWNER"``).
    """
    return Enum(
        enum_cls,
        name=name,
        native_enum=False,
        create_constraint=True,
        length=length,
        validate_strings=True,
        values_callable=lambda cls: [member.value for member in cls],
    )

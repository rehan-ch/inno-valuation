import uuid
from typing import Annotated, Self

from pydantic import (
    AfterValidator,
    BaseModel,
    HttpUrl,
    StringConstraints,
    UrlConstraints,
    model_validator,
)

from app.core.permissions import OrgContext, OrgRole
from app.models.enums import OrganisationStatus
from app.schemas.common import Email, RequestModel


def _blank_to_none(value: str | None) -> str | None:
    return value or None


ShortText = Annotated[
    Annotated[str, StringConstraints(strip_whitespace=True, max_length=200)] | None,
    AfterValidator(_blank_to_none),
]
Band = Annotated[
    Annotated[str, StringConstraints(strip_whitespace=True, max_length=50)] | None,
    AfterValidator(_blank_to_none),
]
LongText = Annotated[
    Annotated[str, StringConstraints(strip_whitespace=True, max_length=5000)] | None,
    AfterValidator(_blank_to_none),
]
OrganisationName = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200)
]
CountryCode = Annotated[str, StringConstraints(pattern=r"^[A-Z]{2}$")]  # ISO 3166-1 alpha-2
CurrencyCode = Annotated[str, StringConstraints(pattern=r"^[A-Z]{3}$")]  # ISO 4217


class OrganisationOut(BaseModel):
    id: uuid.UUID
    name: str
    description: str | None
    industry: str | None
    country: str | None
    size_band: str | None
    revenue_band: str | None
    founder_names: str | None
    website: str | None
    primary_contact_name: str | None
    primary_contact_email: str | None
    currency: str
    status: OrganisationStatus
    # The caller's role here, so the UI can show or hide edit controls.
    role: OrgRole


def organisation_out(ctx: OrgContext) -> OrganisationOut:
    org = ctx.organisation
    return OrganisationOut(
        id=org.id,
        name=org.name,
        description=org.description,
        industry=org.industry,
        country=org.country,
        size_band=org.size_band,
        revenue_band=org.revenue_band,
        founder_names=org.founder_names,
        website=org.website,
        primary_contact_name=org.primary_contact_name,
        primary_contact_email=org.primary_contact_email,
        currency=org.currency,
        status=org.status,
        role=ctx.role,
    )


# Fields that may be left out but never cleared.
_REQUIRED_WHEN_SENT = ("name", "currency")


class OrganisationUpdateIn(RequestModel):
    """Partial update: only the fields sent are changed. Send null to clear an optional field."""

    name: OrganisationName | None = None
    description: LongText = None
    industry: Annotated[
        Annotated[str, StringConstraints(strip_whitespace=True, max_length=100)] | None,
        AfterValidator(_blank_to_none),
    ] = None
    country: CountryCode | None = None
    size_band: Band = None
    revenue_band: Band = None
    founder_names: LongText = None
    website: Annotated[HttpUrl, UrlConstraints(max_length=500)] | None = None
    primary_contact_name: ShortText = None
    primary_contact_email: Email | None = None
    currency: CurrencyCode | None = None

    @model_validator(mode="after")
    def _required_fields_not_cleared(self) -> Self:
        for field in _REQUIRED_WHEN_SENT:
            if field in self.model_fields_set and getattr(self, field) is None:
                raise ValueError(f"{field} cannot be empty")
        return self

    def changes(self) -> dict[str, object]:
        """The fields the client sent, ready to store (URLs as strings)."""
        values: dict[str, object] = {}
        for field in sorted(self.model_fields_set):
            value = getattr(self, field)
            values[field] = str(value) if isinstance(value, HttpUrl) else value
        return values

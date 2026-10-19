"""Structural rules every table must follow. Reads the metadata only, no database."""

from sqlalchemy import DateTime, PrimaryKeyConstraint, Table, UniqueConstraint

import app.models  # noqa: F401  (registers every model)
from app.db.base import Base

CLIENT_TABLES = {
    "memberships",
    "invitations",
    "consultant_grants",
    "audit_events",
    "readiness_assessments",
    "readiness_responses",
    "readiness_consensus",
    "readiness_results",
}


def _tables() -> list[Table]:
    return list(Base.metadata.sorted_tables)


def _leading_index_columns(table: Table) -> set[str]:
    """Columns that lead some full index or unique constraint, so lookups on them are indexed.

    Partial indexes do not count: they cover only some rows.
    """
    leading = {
        next(iter(index.columns)).name
        for index in table.indexes
        if index.columns and index.dialect_options["postgresql"]["where"] is None
    }
    for constraint in table.constraints:
        if isinstance(constraint, UniqueConstraint | PrimaryKeyConstraint) and constraint.columns:
            leading.add(next(iter(constraint.columns)).name)
    return leading


def test_every_foreign_key_is_indexed() -> None:
    missing = [
        f"{table.name}.{fk.parent.name}"
        for table in _tables()
        for fk in table.foreign_keys
        if fk.parent.name not in _leading_index_columns(table)
    ]
    assert missing == []


def test_every_foreign_key_has_deliberate_ondelete() -> None:
    missing = [
        f"{table.name}.{fk.parent.name}"
        for table in _tables()
        for fk in table.foreign_keys
        if fk.ondelete is None
    ]
    assert missing == []


def test_every_timestamp_is_timezone_aware() -> None:
    naive = [
        f"{table.name}.{column.name}"
        for table in _tables()
        for column in table.columns
        if isinstance(column.type, DateTime) and not column.type.timezone
    ]
    assert naive == []


def test_client_tables_reference_their_organisation() -> None:
    with_org = {table.name for table in _tables() if "organisation_id" in table.columns}
    assert with_org == CLIENT_TABLES
    for name in CLIENT_TABLES:
        column = Base.metadata.tables[name].columns["organisation_id"]
        assert {fk.column.table.name for fk in column.foreign_keys} == {"organisations"}

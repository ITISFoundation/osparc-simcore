from typing import Final

import sqlalchemy as sa

from ..constants import DECIMAL_PLACES


class RefActions:
    """Referential actions for `ON UPDATE`, `ON DELETE`"""

    # SEE https://docs.sqlalchemy.org/en/20/core/constraints.html#on-update-on-delete
    CASCADE: Final[str] = "CASCADE"
    SET_NULL: Final[str] = "SET NULL"
    SET_DEFAULT: Final[str] = "SET DEFAULT"
    RESTRICT: Final[str] = "RESTRICT"
    NO_ACTION: Final[str] = "NO ACTION"


def column_created_datetime(*, timezone: bool = True) -> sa.Column:
    return sa.Column(
        "created",
        sa.DateTime(timezone=timezone),
        nullable=False,
        server_default=sa.sql.func.now(),
        doc="Timestamp auto-generated upon creation",
    )


def column_modified_datetime(*, timezone: bool = True) -> sa.Column:
    return sa.Column(
        "modified",
        sa.DateTime(timezone=timezone),
        nullable=False,
        server_default=sa.sql.func.now(),
        onupdate=sa.sql.func.now(),
        doc="Timestamp with last row update",
    )


def column_created_by_user(
    *, users_table: sa.Table, required: bool = False
) -> sa.Column:
    return sa.Column(
        "created_by",
        sa.Integer,
        sa.ForeignKey(
            users_table.c.id,
            onupdate=RefActions.CASCADE,
            ondelete=RefActions.SET_NULL,
        ),
        nullable=not required,
        doc="Who created this row at `created`",
    )


def column_modified_by_user(
    *, users_table: sa.Table, required: bool = False
) -> sa.Column:
    return sa.Column(
        "modified_by",
        sa.Integer,
        sa.ForeignKey(
            users_table.c.id,
            onupdate=RefActions.CASCADE,
            ondelete=RefActions.SET_NULL,
        ),
        nullable=not required,
        doc="Who modified this row at `modified`",
    )


def column_trashed_datetime(resource_name: str) -> sa.Column:
    return sa.Column(
        "trashed",
        sa.DateTime(timezone=True),
        nullable=True,
        comment=f"The date and time when the {resource_name} was marked as trashed. "
        f"Null if the {resource_name} has not been trashed [default].",
    )


def column_trashed_by_user(resource_name: str, users_table: sa.Table) -> sa.Column:
    return sa.Column(
        "trashed_by",
        sa.BigInteger,
        sa.ForeignKey(
            users_table.c.id,
            onupdate=RefActions.CASCADE,
            ondelete=RefActions.SET_NULL,
            name=f"fk_{resource_name}_trashed_by_user_id",
        ),
        nullable=True,
        comment=f"User who trashed the {resource_name}, or null if not trashed or user is unknown.",
    )


_TRIGGER_NAME: Final[str] = "auto_update_modified_timestamp"


def register_modified_datetime_auto_update_trigger(table: sa.Table) -> None:
    """registers a trigger/procedure couple in order to ensure auto
    update of the 'modified' timestamp column when a row is modified.

    NOTE: Add a *hard-coded* version in the alembic migration code!!!
    SEE https://github.com/ITISFoundation/osparc-simcore/blob/78bc54e5815e8be5a8ed6a08a7bbe5591bbd2bd9/packages/postgres-database/src/simcore_postgres_database/migration/versions/e0a2557dec27_add_services_limitations.py


    Arguments:
        table -- the table to add the auto-trigger to
    """
    assert "modified" in table.columns  # nosec

    # NOTE: scoped on database
    procedure_name: Final[str] = f"{table.name}_auto_update_modified_timestamp()"

    # TRIGGER
    modified_timestamp_trigger = sa.DDL(
        f"""
    DROP TRIGGER IF EXISTS {_TRIGGER_NAME} on {table.name};
    CREATE TRIGGER {_TRIGGER_NAME}
    BEFORE INSERT OR UPDATE ON {table.name}
    FOR EACH ROW EXECUTE PROCEDURE {procedure_name};
        """
    )
    # PROCEDURE
    update_modified_timestamp_procedure = sa.DDL(
        f"""
    CREATE OR REPLACE FUNCTION {procedure_name}
    RETURNS TRIGGER AS $$
    BEGIN
    NEW.modified := current_timestamp;
    RETURN NEW;
    END;
    $$ LANGUAGE plpgsql;
        """
    )

    # REGISTER THEM PROCEDURES/TRIGGERS
    sa.event.listen(table, "after_create", update_modified_timestamp_procedure)
    sa.event.listen(table, "after_create", modified_timestamp_trigger)


NUMERIC_KWARGS = {"scale": DECIMAL_PLACES}

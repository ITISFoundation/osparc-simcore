from typing import Final

import sqlalchemy as sa

from ..constants import DECIMAL_PLACES


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


_TRIGGER_NAME: Final[str] = "auto_update_modified_timestamp"


def register_modified_datetime_auto_update_trigger(table: sa.Table) -> None:
    """registers a trigger/procedure couple in order to ensure auto
    update of the 'modified' timestamp column when a row is modified.

    NOTE: Add a *hard-coded* version in the alembic migration code!!!
    see [this example](https://github.com/ITISFoundation/osparc-simcore/blob/78bc54e5815e8be5a8ed6a08a7bbe5591bbd2bd9/packages/postgres-database/src/simcore_postgres_database/migration/versions/e0a2557dec27_add_services_limitations.py)


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

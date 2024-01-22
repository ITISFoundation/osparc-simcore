import sqlalchemy as sa
import sqlalchemy.sql
from sqlalchemy.dialects.postgresql import ARRAY, INTEGER

from .models.services import services_meta_data


def create_select_latest_services_query(
    column_version_label: str = "latest",
) -> sqlalchemy.sql.Select:
    """
    Returns select query of service_meta_data table with columns 'key' and 'latest' (=version)
    """
    assert issubclass(INTEGER, sa.Integer)  # nosec

    return sa.select(
        services_meta_data.c.key,
        sa.func.array_to_string(
            sa.func.max(
                sa.func.string_to_array(services_meta_data.c.version, ".").cast(
                    ARRAY(INTEGER)
                )
            ),
            ".",
        ).label(column_version_label),
    ).group_by(services_meta_data.c.key)

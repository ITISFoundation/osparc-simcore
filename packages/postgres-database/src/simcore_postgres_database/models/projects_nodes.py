""" Groups table

    - List of groups in the framework
    - Groups have a ID, name and a list of users that belong to the group
"""


import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

from ._common import (
    column_created_datetime,
    column_modified_datetime,
    register_modified_datetime_auto_update_trigger,
)
from .base import metadata

projects_nodes = sa.Table(
    "projects_nodes",
    metadata,
    sa.Column(
        "node_id",
        sa.String,
        nullable=False,
        primary_key=True,
        doc="The node unique identifier",
    ),
    sa.Column(
        "required_resources",
        JSONB,
        nullable=False,
        server_default=sa.text("'{}'::jsonb"),
        doc="The node required resources",
    ),
    # TIME STAMPS ----
    column_created_datetime(timezone=True),
    column_modified_datetime(timezone=True),
)


register_modified_datetime_auto_update_trigger(projects_nodes)

""" Groups table

    - List of groups in the framework
    - Groups have a ID, name and a list of users that belong to the group
"""

import sqlalchemy as sa

from ._common import (
    RefActions,
    column_created_datetime,
    column_modified_datetime,
    register_modified_datetime_auto_update_trigger,
)
from .base import metadata
from .projects_nodes import projects_nodes

projects_node_to_pricing_unit = sa.Table(
    "projects_node_to_pricing_unit",
    metadata,
    sa.Column(
        "project_node_id",
        sa.BIGINT,
        sa.ForeignKey(
            projects_nodes.c.project_node_id,
            onupdate=RefActions.CASCADE,
            ondelete=RefActions.CASCADE,
            name="fk_projects_nodes__project_node_to_pricing_unit__uuid",
        ),
        nullable=False,
        doc="The project node unique identifier",
    ),
    sa.Column(
        "pricing_plan_id",
        sa.BigInteger,
        nullable=False,
        doc="The pricing plan unique identifier",
    ),
    sa.Column(
        "pricing_unit_id",
        sa.BigInteger,
        nullable=False,
        doc="The pricing unit unique identifier",
    ),
    # TIME STAMPS ----
    column_created_datetime(timezone=True),
    column_modified_datetime(timezone=True),
    sa.UniqueConstraint("project_node_id"),
)


register_modified_datetime_auto_update_trigger(projects_nodes)

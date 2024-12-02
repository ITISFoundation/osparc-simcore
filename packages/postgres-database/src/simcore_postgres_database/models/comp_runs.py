""" Computational Runs Table

"""

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

from ._common import RefActions, column_created_datetime, column_modified_datetime
from .base import metadata
from .comp_pipeline import StateType

comp_runs = sa.Table(
    "comp_runs",
    metadata,
    # this task db id
    sa.Column(
        "run_id",
        sa.BigInteger,
        nullable=False,
        autoincrement=True,
        primary_key=True,
        doc="Primary key, identifies the run",
    ),
    sa.Column(
        "project_uuid",
        sa.String,
        sa.ForeignKey(
            "projects.uuid",
            name="fk_comp_runs_project_uuid_projects",
            onupdate=RefActions.CASCADE,
            ondelete=RefActions.CASCADE,
        ),
        nullable=False,
        doc="The project uuid with which the run entry is associated",
    ),
    sa.Column(
        "user_id",
        sa.BigInteger(),
        sa.ForeignKey(
            "users.id",
            name="fk_comp_runs_user_id_users",
            onupdate=RefActions.CASCADE,
            ondelete=RefActions.CASCADE,
        ),
        nullable=False,
        doc="The user id with which the run entry is associated",
    ),
    sa.Column(
        "cluster_id",
        sa.BigInteger(),
        sa.ForeignKey(
            "clusters.id",
            name="fk_comp_runs_cluster_id_clusters",
            onupdate=RefActions.CASCADE,
            ondelete=RefActions.SET_NULL,
        ),
        nullable=True,
        doc="The cluster id on which the run entry is associated, if NULL or 0 uses the default",
    ),
    sa.Column(
        "iteration",
        sa.BigInteger,
        nullable=False,
        autoincrement=False,
        doc="A computational run is always associated to a user, a project and a specific iteration",
    ),
    sa.Column(
        "result",
        sa.Enum(StateType),
        nullable=False,
        server_default=StateType.NOT_STARTED.value,
        doc="The result of the run entry",
    ),
    # dag node id and class
    column_created_datetime(timezone=True),
    column_modified_datetime(timezone=True),
    # utc timestamps for submission/start/end
    sa.Column(
        "started",
        sa.DateTime(timezone=True),
        nullable=True,
        doc="When the run was started",
    ),
    sa.Column(
        "ended",
        sa.DateTime(timezone=True),
        nullable=True,
        doc="When the run was finished",
    ),
    sa.Column(
        "cancelled",
        sa.DateTime(timezone=True),
        nullable=True,
        doc="If filled, when cancellation was requested",
    ),
    sa.Column(
        "scheduled",
        sa.DateTime(timezone=True),
        nullable=True,
        doc="last time the pipeline was scheduled to be processed",
    ),
    sa.Column(
        "processed",
        sa.DateTime(timezone=True),
        nullable=True,
        doc="last time the pipeline was actually processed",
    ),
    sa.Column("metadata", JSONB, nullable=True, doc="the run optional metadata"),
    sa.Column(
        "use_on_demand_clusters",
        sa.Boolean(),
        nullable=False,
        doc="the run uses on demand clusters",
    ),
    sa.UniqueConstraint("project_uuid", "user_id", "iteration"),
)

""" Computational Runs Table

"""
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.sql import func

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
            onupdate="CASCADE",
            ondelete="CASCADE",
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
            onupdate="CASCADE",
            ondelete="CASCADE",
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
            onupdate="CASCADE",
            ondelete="SET NULL",
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
    sa.Column(
        "created",
        sa.DateTime(),
        nullable=False,
        server_default=func.now(),
        doc="When the run entry was created",
    ),
    sa.Column(
        "modified",
        sa.DateTime(),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),  # this will auto-update on modification
        doc="When the run entry was last modified",
    ),
    # utc timestamps for submission/start/end
    sa.Column(
        "started",
        sa.DateTime,
        nullable=True,
        doc="When the run was started",
    ),
    sa.Column(
        "ended",
        sa.DateTime,
        nullable=True,
        doc="When the run was finished",
    ),
    sa.Column("metadata", JSONB, nullable=True, doc="the run optional metadata"),
    sa.UniqueConstraint("project_uuid", "user_id", "iteration"),
)

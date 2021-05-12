""" Computational Runs Table

"""
import sqlalchemy as sa
from sqlalchemy.sql import func

from .base import metadata
from .comp_pipeline import StateType

comp_runs = sa.Table(
    "comp_runs",
    metadata,
    # this task db id
    sa.Column(
        "run_id", sa.BigInteger, nullable=False, autoincrement=True, primary_key=True
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
    ),
    sa.Column(
        "iteration",
        sa.BigInteger,
        nullable=False,
        autoincrement=False,
    ),
    sa.Column(
        "result",
        sa.Enum(StateType),
        nullable=False,
        server_default=StateType.NOT_STARTED.value,
    ),
    # dag node id and class
    sa.Column("created", sa.DateTime(), nullable=False, server_default=func.now()),
    sa.Column(
        "modified",
        sa.DateTime(),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),  # this will auto-update on modification
    ),
    # utc timestamps for submission/start/end
    sa.Column("start", sa.DateTime),
    sa.Column("end", sa.DateTime),
    sa.UniqueConstraint("project_uuid", "user_id", "iteration"),
)

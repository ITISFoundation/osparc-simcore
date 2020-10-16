""" Computational Pipeline Table

"""
import enum
import uuid

import sqlalchemy as sa

from .base import metadata


class StateType(enum.Enum):
    NOT_STARTED = "NOT_STARTED"
    PUBLISHED = "PUBLISHED"
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    SUCCESS = "SUCCESS"
    FAILED = "FAILED"


def _new_uuid():
    return str(uuid.uuid4())


comp_pipeline = sa.Table(
    "comp_pipeline",
    metadata,
    sa.Column("project_id", sa.String, primary_key=True, default=_new_uuid),
    sa.Column("dag_adjacency_list", sa.JSON),
    sa.Column(
        "state",
        sa.Enum(StateType),
        nullable=False,
        server_default=StateType.NOT_STARTED.value,
    ),
)

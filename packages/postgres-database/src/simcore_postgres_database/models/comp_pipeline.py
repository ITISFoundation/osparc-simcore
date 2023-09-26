""" Computational Pipeline Table

"""
import enum
import uuid

import sqlalchemy as sa

from .base import metadata


class StateType(enum.Enum):
    """Discrete states in a task lifecycle

    NOTE: these states are the exact same ones as the models-library (RunningState for a project's execution state)
    """

    NOT_STARTED = "NOT_STARTED"
    PUBLISHED = "PUBLISHED"
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    SUCCESS = "SUCCESS"
    FAILED = "FAILED"
    ABORTED = "ABORTED"
    WAITING_FOR_RESOURCES = "WAITING_FOR_RESOURCES"
    WAITING_FOR_CLUSTER = "WAITING_FOR_CLUSTER"


def _new_uuid():
    return str(uuid.uuid4())


comp_pipeline = sa.Table(
    "comp_pipeline",
    metadata,
    sa.Column(
        "project_id",
        sa.String,
        primary_key=True,
        default=_new_uuid,
        doc="Project ID including this pipeline",
    ),
    sa.Column(
        "dag_adjacency_list", sa.JSON, doc="Adjancey list for the pipeline's graph"
    ),
    sa.Column(
        "state",
        sa.Enum(StateType),
        nullable=False,
        server_default=StateType.NOT_STARTED.value,
        doc="Current state of this pipeline",
    ),
)

""" Computational Tasks Table

"""
import sqlalchemy as sa

from .base import metadata
from .comp_pipeline import UNKNOWN

comp_tasks = sa.Table(
    "comp_tasks",
    metadata,
    # this task db id
    sa.Column("task_id", sa.Integer, primary_key=True),
    sa.Column("project_id", sa.String, sa.ForeignKey("comp_pipeline.project_id")),
    # dag node id
    sa.Column("node_id", sa.String),
    # celery task id
    sa.Column("job_id", sa.String),
    # internal id (better for debugging, nodes from 1 to N)
    sa.Column("internal_id", sa.Integer),
    sa.Column("schema", sa.JSON),
    sa.Column("inputs", sa.JSON),
    sa.Column("outputs", sa.JSON),
    sa.Column("image", sa.JSON),
    sa.Column("state", sa.Integer, default=UNKNOWN),
    # utc timestamps for submission/start/end
    sa.Column("submit", sa.DateTime),
    sa.Column("start", sa.DateTime),
    sa.Column("end", sa.DateTime),

    sa.UniqueConstraint('project_id', 'node_id', name='project_node_uniqueness'),
)

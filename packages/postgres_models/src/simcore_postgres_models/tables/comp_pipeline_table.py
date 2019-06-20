
import uuid

import sqlalchemy as sa

from .base import metadata

UNKNOWN = 0
PENDING = 1
RUNNING = 2
SUCCESS = 3
FAILED = 4

comp_pipeline = sa.Table("comp_pipeline", metadata,
    sa.Column("project_id", sa.String, primary_key=True, default=str(uuid.uuid4())),
    sa.Column("dag_adjacency_list", sa.JSON),
    sa.Column("state", sa.Column(sa.String, default=UNKNOWN))
)

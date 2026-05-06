import sqlalchemy as sa

from ._common import (
    RefActions,
    column_created_datetime,
    column_modified_datetime,
)
from .base import metadata

nodes_pending_deletion = sa.Table(
    # Outbox of project-nodes whose storage assets (S3 objects + file_meta_data
    # rows in the storage service) still need to be cleaned up. A row lives
    # here from the moment a node deletion is requested until the storage
    # cleanup confirms success (then the row is removed). Rows that
    # repeatedly fail are surfaced via `attempts` / `last_error` for ops.
    #
    # NOTE: deliberately NO foreign key to `projects.uuid` — the outbox row
    # must survive scenarios where the project row gets deleted out-of-band
    # so the retry task can still drive the storage cleanup to completion.
    "nodes_pending_deletion",
    metadata,
    sa.Column(
        "project_uuid",
        sa.String,
        nullable=False,
        doc="UUID of the project that owned the deleted node",
    ),
    sa.Column(
        "node_id",
        sa.String,
        nullable=False,
        doc="UUID of the node whose storage cleanup is still pending",
    ),
    sa.Column(
        "requested_by",
        sa.BigInteger,
        sa.ForeignKey(
            "users.id",
            name="fk_nodes_pending_deletion_requested_by_users",
            onupdate=RefActions.CASCADE,
            ondelete=RefActions.SET_NULL,
        ),
        nullable=True,
        doc="User who requested the node deletion (null if user later removed)",
    ),
    sa.Column(
        "attempts",
        sa.Integer,
        nullable=False,
        server_default=sa.text("0"),
        doc="Number of cleanup attempts performed so far",
    ),
    sa.Column(
        "last_attempt_at",
        sa.DateTime(timezone=True),
        nullable=True,
        doc="Timestamp of the last cleanup attempt (null until the first run)",
    ),
    sa.Column(
        "last_error",
        sa.String,
        nullable=True,
        doc="Human-readable error from the most recent failed attempt",
    ),
    sa.Column(
        "storage_task_uuid",
        sa.String,
        nullable=True,
        doc="UUID of the storage celery task currently driving the cleanup, or null when no task is in flight",
    ),
    column_created_datetime(timezone=True),
    column_modified_datetime(timezone=True),
    sa.PrimaryKeyConstraint("project_uuid", "node_id", name="nodes_pending_deletion_pk"),
)

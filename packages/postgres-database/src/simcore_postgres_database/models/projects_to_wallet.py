import sqlalchemy as sa

from ._common import column_created_datetime, column_modified_datetime
from .base import metadata
from .projects import projects
from .wallets import wallets

projects_to_wallet = sa.Table(
    "projects_to_wallet",
    metadata,
    sa.Column(
        "project_uuid",
        sa.String,
        sa.ForeignKey(
            projects.c.uuid,
            name="fk_projects_comments_project_uuid",
            ondelete="CASCADE",
            onupdate="CASCADE",
        ),
        index=True,
        primary_key=True,
        nullable=False,
        doc="project reference for this table",
    ),
    sa.Column(
        "wallet_id",
        sa.BigInteger,
        sa.ForeignKey(
            wallets.c.id,
            name="fk_projects_wallet_wallets_id",
            ondelete="CASCADE",
            onupdate="CASCADE",
        ),
        nullable=False,
    ),
    column_created_datetime(timezone=True),
    column_modified_datetime(timezone=True),
)

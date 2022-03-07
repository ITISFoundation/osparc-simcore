import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

from .base import metadata
from .projects import projects

sharing_networks = sa.Table(
    "sharing_networks",
    metadata,
    sa.Column(
        "project_uuid",
        sa.String,
        sa.ForeignKey(
            projects.c.uuid,
            name="fk_sharing_networks_project_uuid",
            ondelete="CASCADE",
            onupdate="CASCADE",
        ),
        primary_key=True,
        doc="project reference and primary key for this table",
    ),
    sa.Column(
        "networks_with_aliases",
        JSONB,
        nullable=False,
        server_default=sa.text("'{}'::jsonb"),
        doc="Maps networks with attached services by node_id and alias",
    ),
)

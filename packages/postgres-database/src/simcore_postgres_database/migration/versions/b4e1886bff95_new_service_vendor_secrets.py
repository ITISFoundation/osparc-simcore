"""New service vendor secrets

Revision ID: b4e1886bff95
Revises: 0c084cb1091c
Create Date: 2023-06-01 15:41:23.571011+00:00

"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "b4e1886bff95"
down_revision = "0c084cb1091c"
branch_labels = None
depends_on = None


def upgrade():

    op.create_table(
        "services_vendor_secrets",
        sa.Column("service_key", sa.String(), nullable=False),
        sa.Column("service_base_version", sa.String(), nullable=False),
        sa.Column(
            "secrets_map",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column(
            "created",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "modified",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["service_key", "service_base_version"],
            ["services_meta_data.key", "services_meta_data.version"],
            onupdate="CASCADE",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint(
            "service_key", "service_base_version", name="services_vendor_secrets_pk"
        ),
    )


def downgrade():

    op.drop_table("services_vendor_secrets")

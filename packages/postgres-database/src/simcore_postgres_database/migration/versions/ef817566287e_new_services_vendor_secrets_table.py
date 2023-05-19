"""new services_vendor_secrets table

Revision ID: ef817566287e
Revises: 0c084cb1091c
Create Date: 2023-05-18 11:38:51.671239+00:00

"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "ef817566287e"
down_revision = "0c084cb1091c"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "services_vendor_secrets",
        sa.Column("service_key", sa.String(), nullable=False),
        sa.Column(
            "secrets_map",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column(
            "created", sa.DateTime(), server_default=sa.text("now()"), nullable=False
        ),
        sa.Column(
            "modified", sa.DateTime(), server_default=sa.text("now()"), nullable=False
        ),
        sa.PrimaryKeyConstraint(
            "service_key", name="services_vendor_secrets_service_key_pk"
        ),
    )


def downgrade():
    op.drop_table("services_vendor_secrets")

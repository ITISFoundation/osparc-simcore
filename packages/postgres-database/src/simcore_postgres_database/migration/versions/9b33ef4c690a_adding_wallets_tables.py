"""adding wallets tables

Revision ID: 9b33ef4c690a
Revises: afc752d10a6c
Create Date: 2023-07-31 11:40:38.764685+00:00

"""
import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "9b33ef4c690a"
down_revision = "afc752d10a6c"
branch_labels = None
depends_on = None


# ------------------------ TRIGGERS
wallet_trigger = sa.DDL(
    """
DROP TRIGGER IF EXISTS wallet_modification on wallets;
CREATE TRIGGER wallet_modification
AFTER INSERT ON wallets
    FOR EACH ROW
    EXECUTE PROCEDURE set_wallet_to_owner_group();
"""
)


# --------------------------- PROCEDURES
assign_wallet_access_rights_to_owner_group_procedure = sa.DDL(
    """
CREATE OR REPLACE FUNCTION set_wallet_to_owner_group() RETURNS TRIGGER AS $$
DECLARE
    group_id BIGINT;
BEGIN
    IF TG_OP = 'INSERT' THEN
        INSERT INTO "wallet_to_groups" ("gid", "wallet_id", "read", "write", "delete") VALUES (NEW.owner, NEW.wallet_id, TRUE, TRUE, TRUE);
    END IF;
    RETURN NULL;
END; $$ LANGUAGE 'plpgsql';
    """
)


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.create_table(
        "wallets",
        sa.Column("wallet_id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("description", sa.String(), nullable=True),
        sa.Column("owner", sa.BigInteger(), nullable=False),
        sa.Column("thumbnail", sa.String(), nullable=True),
        sa.Column(
            "status", sa.Enum("ACTIVE", "INACTIVE", name="walletstatus"), nullable=False
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
            ["owner"],
            ["groups.gid"],
            name="fk_wallets_gid_groups",
            onupdate="CASCADE",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("wallet_id"),
    )
    op.create_table(
        "wallet_to_groups",
        sa.Column("wallet_id", sa.BigInteger(), nullable=True),
        sa.Column("gid", sa.BigInteger(), nullable=True),
        sa.Column(
            "read", sa.Boolean(), server_default=sa.text("false"), nullable=False
        ),
        sa.Column(
            "write", sa.Boolean(), server_default=sa.text("false"), nullable=False
        ),
        sa.Column(
            "delete", sa.Boolean(), server_default=sa.text("false"), nullable=False
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
            ["gid"],
            ["groups.gid"],
            name="fk_wallet_to_groups_gid_groups",
            onupdate="CASCADE",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["wallet_id"],
            ["wallets.wallet_id"],
            name="fk_wallet_to_groups_id_wallets",
            onupdate="CASCADE",
            ondelete="CASCADE",
        ),
        sa.UniqueConstraint("wallet_id", "gid"),
    )
    op.create_table(
        "projects_to_wallet",
        sa.Column("project_uuid", sa.String(), nullable=False),
        sa.Column("wallet_id", sa.BigInteger(), nullable=False),
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
            ["project_uuid"],
            ["projects.uuid"],
            name="fk_projects_comments_project_uuid",
            onupdate="CASCADE",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["wallet_id"],
            ["wallets.wallet_id"],
            name="fk_projects_wallet_wallets_id",
            onupdate="CASCADE",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("project_uuid"),
    )
    op.create_index(
        op.f("ix_projects_to_wallet_project_uuid"),
        "projects_to_wallet",
        ["project_uuid"],
        unique=False,
    )
    # ### end Alembic commands ###
    op.execute(assign_wallet_access_rights_to_owner_group_procedure)
    op.execute(wallet_trigger)


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_index(
        op.f("ix_projects_to_wallet_project_uuid"), table_name="projects_to_wallet"
    )
    op.drop_table("projects_to_wallet")
    op.drop_table("wallet_to_groups")
    op.drop_table("wallets")
    # ### end Alembic commands ###
    op.execute(assign_wallet_access_rights_to_owner_group_procedure)
    op.execute(wallet_trigger)

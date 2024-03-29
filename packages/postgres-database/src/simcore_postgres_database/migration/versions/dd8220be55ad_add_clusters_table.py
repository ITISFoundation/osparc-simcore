"""add clusters table

Revision ID: dd8220be55ad
Revises: 5860ac6ad178
Create Date: 2021-08-23 13:00:25.803959+00:00

"""
import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "dd8220be55ad"
down_revision = "5860ac6ad178"
branch_labels = None
depends_on = None

# ------------------------ TRIGGERS
new_cluster_trigger = sa.DDL(
    """
DROP TRIGGER IF EXISTS cluster_modification on clusters;
CREATE TRIGGER cluster_modification
AFTER INSERT ON clusters
    FOR EACH ROW
    EXECUTE PROCEDURE set_cluster_to_owner_group();
"""
)


# --------------------------- PROCEDURES
assign_cluster_access_rights_to_owner_group_procedure = sa.DDL(
    """
CREATE OR REPLACE FUNCTION set_cluster_to_owner_group() RETURNS TRIGGER AS $$
DECLARE
    group_id BIGINT;
BEGIN
    IF TG_OP = 'INSERT' THEN
        INSERT INTO "cluster_to_groups" ("gid", "cluster_id", "read_access", "write_access", "delete_access") VALUES (NEW.owner, NEW.id, TRUE, TRUE, TRUE);
    END IF;
    RETURN NULL;
END; $$ LANGUAGE 'plpgsql';
    """
)


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.create_table(
        "clusters",
        sa.Column("id", sa.BigInteger(), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("description", sa.String(), nullable=True),
        sa.Column(
            "type", sa.Enum("AWS", "ON_PREMISE", name="clustertype"), nullable=False
        ),
        sa.Column("owner", sa.BigInteger(), nullable=False),
        sa.Column(
            "thumbnail",
            sa.String,
            nullable=True,
            doc="Link to image as to cluster thumbnail",
        ),
        sa.Column(
            "created", sa.DateTime(), server_default=sa.text("now()"), nullable=False
        ),
        sa.Column(
            "modified", sa.DateTime(), server_default=sa.text("now()"), nullable=False
        ),
        sa.ForeignKeyConstraint(
            ["owner"],
            ["groups.gid"],
            name="fk_clusters_gid_groups",
            onupdate="CASCADE",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "cluster_to_groups",
        sa.Column("cluster_id", sa.BigInteger(), nullable=True),
        sa.Column("gid", sa.BigInteger(), nullable=True),
        sa.Column(
            "read_access", sa.Boolean(), server_default=sa.text("false"), nullable=False
        ),
        sa.Column(
            "write_access",
            sa.Boolean(),
            server_default=sa.text("false"),
            nullable=False,
        ),
        sa.Column(
            "delete_access",
            sa.Boolean(),
            server_default=sa.text("false"),
            nullable=False,
        ),
        sa.Column(
            "created", sa.DateTime(), server_default=sa.text("now()"), nullable=False
        ),
        sa.Column(
            "modified", sa.DateTime(), server_default=sa.text("now()"), nullable=False
        ),
        sa.ForeignKeyConstraint(
            ["cluster_id"],
            ["clusters.id"],
            name="fk_cluster_to_groups_id_clusters",
            onupdate="CASCADE",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["gid"],
            ["groups.gid"],
            name="fk_cluster_to_groups_gid_groups",
            onupdate="CASCADE",
            ondelete="CASCADE",
        ),
        sa.UniqueConstraint("cluster_id", "gid"),
    )
    # ### end Alembic commands ###
    op.execute(assign_cluster_access_rights_to_owner_group_procedure)
    op.execute(new_cluster_trigger)


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_table("cluster_to_groups")
    op.drop_table("clusters")
    # ### end Alembic commands ###
    op.execute("DROP TYPE IF EXISTS clustertype")
    op.execute("DROP TRIGGER IF EXISTS cluster_modification on clusters;")
    op.execute("DROP FUNCTION set_cluster_to_owner_group() CASCADE")

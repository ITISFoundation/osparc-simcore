"""add tag_to_groups table and rm tag.user_id

Revision ID: 3aa309471ff8
Revises: c3c564121364
Create Date: 2022-11-17 23:21:49.290958+00:00

"""
import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "3aa309471ff8"
down_revision = "c3c564121364"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "tags_to_groups",
        sa.Column("tag_id", sa.BigInteger(), nullable=False),
        sa.Column("group_id", sa.BigInteger(), nullable=False),
        sa.Column("read", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column(
            "write", sa.Boolean(), server_default=sa.text("false"), nullable=False
        ),
        sa.Column(
            "delete", sa.Boolean(), server_default=sa.text("false"), nullable=False
        ),
        sa.Column(
            "created", sa.DateTime(), server_default=sa.text("now()"), nullable=False
        ),
        sa.Column(
            "modified", sa.DateTime(), server_default=sa.text("now()"), nullable=False
        ),
        sa.ForeignKeyConstraint(
            ["group_id"],
            ["groups.gid"],
            name="fk_tag_to_group_group_id",
            onupdate="CASCADE",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["tag_id"],
            ["tags.id"],
            name="fk_tag_to_group_tag_id",
            onupdate="CASCADE",
            ondelete="CASCADE",
        ),
        sa.UniqueConstraint("tag_id", "group_id"),
    )

    # transform every tags.user_id to its PRIMARY group_id in tags_to_groups
    op.execute(
        sa.DDL(
            """
INSERT INTO tags_to_groups (tag_id, group_id) SELECT tags.id, user_to_groups.gid
FROM tags JOIN users ON users.id = tags.user_id JOIN user_to_groups ON users.id = user_to_groups.uid JOIN groups ON groups.gid = user_to_groups.gid AND groups.type = 'PRIMARY'
            """
        )
    )

    # set  full access for PRIMARY group_id
    op.execute(
        sa.DDL(
            """
UPDATE tags_to_groups SET write='True', delete='True', modified=now()
            """
        )
    )

    # Drop old tags.user_id
    op.drop_constraint("tags_user_id_fkey", "tags", type_="foreignkey")
    op.drop_column("tags", "user_id")


def downgrade():
    op.add_column(
        "tags",
        sa.Column("user_id", sa.BIGINT(), autoincrement=False, default=1),
    )
    op.create_foreign_key(
        "tags_user_id_fkey",
        "tags",
        "users",
        ["user_id"],
        ["id"],
        onupdate="CASCADE",
        ondelete="CASCADE",
    )

    # Sets tags.user_id
    op.execute(
        sa.DDL(
            """
    UPDATE tags SET user_id=(SELECT users.id
    FROM users JOIN tags_to_groups ON tags_to_groups.group_id = users.primary_gid
    WHERE tags.id = tags_to_groups.tag_id)
            """
        )
    )
    op.alter_column("tags", "user_id", nullable=False)

    op.drop_table("tags_to_groups")

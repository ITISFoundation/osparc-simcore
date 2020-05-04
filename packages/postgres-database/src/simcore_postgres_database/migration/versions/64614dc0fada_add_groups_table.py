"""add groups table

Revision ID: 64614dc0fada
Revises: 16ee7d73b9cc
Create Date: 2020-04-22 13:42:06.572011+00:00

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "64614dc0fada"
down_revision = "16ee7d73b9cc"
branch_labels = None
depends_on = None


def upgrade():

    set_check_uniqueness_procedure = sa.DDL(
        """
CREATE OR REPLACE FUNCTION check_group_uniqueness(name text, type text) RETURNS INT AS $$
BEGIN
    IF type = 'EVERYONE' AND (SELECT COUNT(*) FROM groups WHERE groups.type = 'EVERYONE') = 1 THEN
        RETURN 127;
    END IF;
    RETURN 0;
END; $$ LANGUAGE 'plpgsql';
"""
    )
    op.execute(set_check_uniqueness_procedure)

    # ### commands auto generated by Alembic - please adjust! ###
    op.create_table(
        "groups",
        sa.Column("gid", sa.BigInteger(), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("description", sa.String(), nullable=False),
        sa.Column(
            "type",
            sa.Enum("STANDARD", "PRIMARY", "EVERYONE", name="grouptype"),
            nullable=False,
            server_default="STANDARD",
        ),
        sa.Column(
            "created", sa.DateTime(), server_default=sa.text("now()"), nullable=False
        ),
        sa.Column(
            "modified", sa.DateTime(), server_default=sa.text("now()"), nullable=False
        ),
        sa.PrimaryKeyConstraint("gid"),
        sa.CheckConstraint("check_group_uniqueness(name, text(type)) = 0"),
    )
    op.create_table(
        "user_to_groups",
        sa.Column("uid", sa.BigInteger(), nullable=True),
        sa.Column("gid", sa.BigInteger(), nullable=True),
        sa.Column(
            "created", sa.DateTime(), server_default=sa.text("now()"), nullable=False
        ),
        sa.Column(
            "modified", sa.DateTime(), server_default=sa.text("now()"), nullable=False
        ),
        sa.ForeignKeyConstraint(
            ["gid"],
            ["groups.gid"],
            name="fk_user_to_groups_gid_groups",
            onupdate="CASCADE",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["uid"],
            ["users.id"],
            name="fk_user_to_groups_id_users",
            onupdate="CASCADE",
            ondelete="CASCADE",
        ),
        sa.UniqueConstraint("uid", "gid"),
    )
    op.add_column(
        "users",
        sa.Column(
            "modified", sa.DateTime(), server_default=sa.text("now()"), nullable=False
        ),
    )
    op.add_column("users", sa.Column("primary_gid", sa.BigInteger(), nullable=True))
    op.create_foreign_key(
        "fk_users_gid_groups",
        "users",
        "groups",
        ["primary_gid"],
        ["gid"],
        onupdate="CASCADE",
        ondelete="RESTRICT",
    )
    # ### end Alembic commands ###

    # manually added migration (adds the procedure and triggers for user/groups)
    new_user_trigger = sa.DDL(
        f"""
DROP TRIGGER IF EXISTS user_modification on users;
CREATE TRIGGER user_modification
AFTER INSERT OR UPDATE OR DELETE ON users
    FOR EACH ROW
    EXECUTE PROCEDURE set_user_groups();
"""
    )

    group_delete_trigger = sa.DDL(
    f"""
DROP TRIGGER IF EXISTS group_delete_trigger on groups;
CREATE TRIGGER group_delete_trigger
BEFORE DELETE ON groups
    FOR EACH ROW
    EXECUTE PROCEDURE group_delete_procedure();
"""
    )

    set_user_groups_procedure = sa.DDL(
        f"""
CREATE OR REPLACE FUNCTION set_user_groups() RETURNS TRIGGER AS $$
DECLARE
    group_id BIGINT;
BEGIN
    IF TG_OP = 'INSERT' THEN
        -- set primary group
        INSERT INTO "groups" ("name", "description", "type") VALUES (NEW.name, 'primary group', 'PRIMARY') RETURNING gid INTO group_id;
        INSERT INTO "user_to_groups" ("uid", "gid") VALUES (NEW.id, group_id);
        UPDATE "users" SET "primary_gid" = group_id WHERE "id" = NEW.id;
        -- set everyone goup        
        INSERT INTO "user_to_groups" ("uid", "gid") VALUES (NEW.id, (SELECT "gid" FROM "groups" WHERE "type" = 'EVERYONE'));
    ELSIF TG_OP = 'UPDATE' THEN
        UPDATE "groups" SET "name" = NEW.name WHERE "gid" = NEW.primary_gid;
    ELSEIF TG_OP = 'DELETE' THEN
        DELETE FROM "groups" WHERE "gid" = OLD.primary_gid;
    END IF;
    RETURN NULL;
END; $$ LANGUAGE 'plpgsql';
"""
    )

    set_add_unique_everyone_group = sa.DDL(
        """
INSERT INTO "groups" ("name", "description", "type") VALUES ('Everyone', 'all users', 'EVERYONE') ON CONFLICT DO NOTHING;
"""
    )

    set_group_delete_procedure = sa.DDL(
    """
CREATE OR REPLACE FUNCTION group_delete_procedure() RETURNS TRIGGER AS $$
BEGIN
    IF OLD.type = 'EVERYONE' THEN
        RAISE EXCEPTION 'Everyone group cannot be deleted';
    END IF;
    RETURN OLD;
END; $$ LANGUAGE 'plpgsql';
"""
    )

    op.execute(set_add_unique_everyone_group)
    op.execute(set_group_delete_procedure)
    op.execute(group_delete_trigger)
    op.execute(set_user_groups_procedure)
    op.execute(new_user_trigger)

    op.alter_column("users", "created_at", server_default=sa.text("now()"))


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_constraint("fk_users_gid_groups", "users", type_="foreignkey")
    op.drop_column("users", "primary_gid")
    op.drop_column("users", "modified")
    op.drop_table("user_to_groups")
    op.drop_table("groups")
    # ### end Alembic commands ###
    # manually added migration
    op.execute("DROP TRIGGER IF EXISTS user_modification on users;")
    op.execute("DROP FUNCTION set_user_groups()")
    op.execute("DROP TRIGGER IF EXISTS group_delete_trigger on groups")
    op.execute("DROP FUNCTION group_delete_procedure()")
    op.execute("DROP FUNCTION check_group_uniqueness(name text, type text)")
    op.alter_column("users", "created_at", server_default=None)

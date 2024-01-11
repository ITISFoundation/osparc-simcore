"""new user names cols

Revision ID: 53d93305d953
Revises: 392a86f2e446
Create Date: 2024-01-11 16:26:50.455150+00:00

"""
import random
import re

import sqlalchemy as sa
from alembic import op
from sqlalchemy.exc import IntegrityError

# revision identifiers, used by Alembic.
revision = "53d93305d953"
down_revision = "392a86f2e446"
branch_labels = None
depends_on = None

SEPARATOR = "."  # Based on this info UserNameConverter: 'first_name.lastname'


def upgrade():

    # new columns
    op.add_column("users", sa.Column("username", sa.String(length=50), nullable=False))
    op.add_column("users", sa.Column("first_name", sa.String(length=50), nullable=True))
    op.add_column("users", sa.Column("last_name", sa.String(length=50), nullable=True))
    op.create_unique_constraint("user_username_ukey", "users", ["username"])

    connection = op.get_bind()

    result = connection.execute(sa.text("SELECT id, name FROM users"))
    for user_id, name in result:
        # from name -> generate username
        user_name = re.sub(r"[^a-zA-Z0-9]", "", name).lower()

        # from name -> create first_name, last_name
        parts = name.split(SEPARATOR, 1)
        first_name = parts[0].capitalize()
        last_name = parts[1].capitalize() if len(parts) == 2 else None

        query = sa.text(
            "UPDATE users SET first_name=:first, last_name=:last, user_name=:uname WHERE id=:id"
        )
        values = {
            "first": first_name,
            "last": last_name,
            "id": user_id,
            "uname": user_name,
        }

        try:
            connection.execute(query, values)
        except IntegrityError:
            values["uname"] = f"{user_name}_{random.randint(1000, 9999)}"  # noqa: S311
            connection.execute(query, values)

    # delete
    op.drop_column("users", "name")


def downgrade():

    op.add_column(
        "users", sa.Column("name", sa.VARCHAR(), autoincrement=False, nullable=False)
    )

    connection = op.get_bind()

    result = connection.execute(sa.text("SELECT id, first_name, last_name FROM users"))

    for user_id, first_name, last_name in result:
        name = f"{first_name or ''}.{last_name or ''}".strip(".")
        connection.execute(
            sa.text("UPDATE users SET name=:name WHERE id=:id"),
            {"name": name, "id": user_id},
        )

    # delete
    op.drop_constraint("user_username_ukey", "users", type_="unique")
    op.drop_column("users", "last_name")
    op.drop_column("users", "first_name")
    op.drop_column("users", "username")

"""new user name cols

Revision ID: f9f9a650bf4b
Revises: 392a86f2e446
Create Date: 2024-01-12 06:29:40.364669+00:00

"""

import re
import secrets
import string

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "f9f9a650bf4b"
down_revision = "392a86f2e446"
branch_labels = None
depends_on = None

SEPARATOR = "."  # Based on this info UserNameConverter: 'first_name.lastname'


def upgrade():
    # new columns
    op.add_column("users", sa.Column("first_name", sa.String(), nullable=True))
    op.add_column("users", sa.Column("last_name", sa.String(), nullable=True))

    # fill new and update existing
    connection = op.get_bind()
    result = connection.execute(sa.text("SELECT id, name FROM users"))

    used = set()

    for user_id, name in result:
        # from name -> generate name
        new_name = re.sub(r"[^a-zA-Z0-9]", "", name).lower()
        while new_name in used:
            new_name += f"{''.join(secrets.choice(string.digits) for _ in range(4))}"

        # from name -> create first_name, last_name
        parts = name.split(SEPARATOR, 1)
        first_name = parts[0].capitalize()
        last_name = parts[1].capitalize() if len(parts) == 2 else None

        query = sa.text(
            "UPDATE users SET first_name=:first, last_name=:last, name=:uname WHERE id=:id"
        )
        values = {
            "first": first_name,
            "last": last_name,
            "id": user_id,
            "uname": new_name,
        }

        connection.execute(query, values)
        used.add(new_name)

    op.create_unique_constraint("user_name_ukey", "users", ["name"])


def downgrade():
    connection = op.get_bind()
    op.drop_constraint("user_name_ukey", "users", type_="unique")

    result = connection.execute(sa.text("SELECT id, first_name, last_name FROM users"))

    for user_id, first_name, last_name in result:
        name = f"{first_name or ''}.{last_name or ''}".strip(".")
        connection.execute(
            sa.text("UPDATE users SET name=:name WHERE id=:id"),
            {"name": name, "id": user_id},
        )

    # delete
    op.drop_column("users", "last_name")
    op.drop_column("users", "first_name")

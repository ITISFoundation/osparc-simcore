"""Checkconstraint filetype

Revision ID: 9014ae5fd6e5
Revises: 4f9c8738178b
Create Date: 2023-03-29 13:52:47.611065+00:00

"""

from alembic import op

# revision identifiers, used by Alembic.
revision = "9014ae5fd6e5"
down_revision = "4f9c8738178b"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("UPDATE services_consume_filetypes SET filetype = UPPER(filetype)")
    op.create_check_constraint(
        "ck_filetype_is_upper",
        "services_consume_filetypes",
        "filetype = upper(filetype)",
    )


def downgrade():
    op.drop_constraint(
        "ck_filetype_is_upper", "services_consume_filetypes", type_="check"
    )

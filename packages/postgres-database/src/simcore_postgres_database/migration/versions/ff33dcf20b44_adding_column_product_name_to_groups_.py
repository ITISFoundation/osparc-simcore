"""adding column product_name to groups_extra_properties

Revision ID: ff33dcf20b44
Revises: e84904303e2b
Create Date: 2023-02-15 14:06:52.562223+00:00

"""
import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "ff33dcf20b44"
down_revision = "e84904303e2b"
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###

    conn = op.get_bind()
    default_product_name = conn.scalar(
        sa.DDL("SELECT name from products ORDER BY priority LIMIT 1")
    )

    op.add_column(
        "groups_extra_properties",
        sa.Column(
            "product_name",
            sa.VARCHAR(),
            nullable=False,
            server_default=default_product_name,
        ),
    )
    op.create_foreign_key(
        "fk_groups_extra_properties_to_products_name",
        "groups_extra_properties",
        "products",
        ["product_name"],
        ["name"],
        onupdate="CASCADE",
        ondelete="CASCADE",
    )
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_constraint(
        "fk_groups_extra_properties_to_products_name",
        "groups_extra_properties",
        type_="foreignkey",
    )
    op.drop_column("groups_extra_properties", "product_name")
    # ### end Alembic commands ###

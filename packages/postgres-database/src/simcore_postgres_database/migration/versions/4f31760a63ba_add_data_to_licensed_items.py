"""add data to licensed_items

Revision ID: 4f31760a63ba
Revises: 1bc517536e0a
Create Date: 2025-01-29 16:51:16.453069+00:00

"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "4f31760a63ba"
down_revision = "1bc517536e0a"
branch_labels = None
depends_on = None


def upgrade():

    with op.batch_alter_table("licensed_items") as batch_op:
        batch_op.alter_column(
            "name",
            new_column_name="licensed_resource_name",
            existing_type=sa.String(),
            nullable=False,
        )
        batch_op.alter_column(
            "pricing_plan_id",
            existing_type=sa.Integer(),
            nullable=True,
        )
        batch_op.alter_column(
            "product_name",
            existing_type=sa.String(),
            nullable=True,
        )

    # ### commands auto generated by Alembic - please adjust! ###
    op.add_column(
        "licensed_items",
        sa.Column(
            "licensed_resource_data",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
        ),
    )
    op.add_column(
        "licensed_items",
        sa.Column(
            "trashed",
            sa.DateTime(timezone=True),
            nullable=True,
            comment="The date and time when the licensed_item was marked as trashed. Null if the licensed_item has not been trashed [default].",
        ),
    )
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_column("licensed_items", "trashed")
    op.drop_column("licensed_items", "licensed_resource_data")
    # ### end Alembic commands ###

    # Delete rows with null values in pricing_plan_id and product_name
    op.execute(
        sa.DDL(
            """
        DELETE FROM licensed_items
        WHERE pricing_plan_id IS NULL OR product_name IS NULL;
        """
        )
    )
    print(
        "Warning: Rows with null values in pricing_plan_id or product_name have been deleted."
    )

    with op.batch_alter_table("licensed_items") as batch_op:

        batch_op.alter_column(
            "product_name",
            existing_type=sa.String(),
            nullable=False,
        )
        batch_op.alter_column(
            "pricing_plan_id",
            existing_type=sa.Integer(),
            nullable=False,
        )
        batch_op.alter_column(
            "licensed_resource_name",
            new_column_name="name",
            existing_type=sa.String(),
            nullable=False,
        )

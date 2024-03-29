"""add_db_extensions

Revision ID: 20d60d2663ad
Revises: f3a5484fe05d
Create Date: 2024-03-04 14:52:51.535716+00:00

"""
from alembic import op

# revision identifiers, used by Alembic.
revision = "20d60d2663ad"
down_revision = "f3a5484fe05d"
branch_labels = None
depends_on = None


def upgrade():
    # Check if the extension exists before attempting to create it
    op.execute(
        """
        DO
        $$
        BEGIN
            IF EXISTS(SELECT * FROM pg_available_extensions WHERE name = 'aws_commons') THEN
                -- Create the extension
                CREATE EXTENSION if not exists aws_commons;
            END IF;
        END
        $$;
    """
    )
    op.execute(
        """
        DO
        $$
        BEGIN
            IF EXISTS(SELECT * FROM pg_available_extensions WHERE name = 'aws_s3') THEN
                -- Create the extension
                CREATE EXTENSION if not exists aws_s3;
            END IF;
        END
        $$;
    """
    )


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    pass
    # ### end Alembic commands ###

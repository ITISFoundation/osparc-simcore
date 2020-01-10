import sqlalchemy as sa

from .base import metadata

tags = sa.Table("tags", metadata,
    sa.Column("id", sa.BigInteger, nullable=False, primary_key=True),
    sa.Column("user_id", sa.BigInteger, sa.ForeignKey("users.id"), nullable=False),
    sa.Column("name", sa.String, nullable=False),
    sa.Column("description", sa.String, nullable=True),
    sa.Column("color", sa.String, nullable=False)
)

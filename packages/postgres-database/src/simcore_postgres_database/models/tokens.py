"""User Tokens table"""

import sqlalchemy as sa
from simcore_postgres_database.models._common import RefActions

from .base import metadata
from .users import users

# NOTE: this is another way of of defining keys ...
tokens = sa.Table(
    "tokens",
    metadata,
    sa.Column("token_id", sa.BigInteger, nullable=False, primary_key=True),
    sa.Column(
        "user_id",
        sa.BigInteger,
        sa.ForeignKey(
            users.c.id, onupdate=RefActions.CASCADE, ondelete=RefActions.CASCADE
        ),
        nullable=False,
    ),
    sa.Column("token_service", sa.String, nullable=False),
    sa.Column("token_data", sa.JSON, nullable=False),
)

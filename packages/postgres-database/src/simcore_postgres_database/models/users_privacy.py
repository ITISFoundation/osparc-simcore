import sqlalchemy as sa
from sqlalchemy.sql import expression

from ._common import RefActions
from .base import metadata
from .users import users

users_privacy = sa.Table(
    "users_privacy",
    metadata,
    sa.Column(
        "user_id",
        sa.Integer,
        sa.ForeignKey(
            users.c.id,
            onupdate=RefActions.CASCADE,
            ondelete=RefActions.CASCADE,
        ),
        nullable=True,
    ),
    # Hide info
    sa.Column(
        "hide_email",
        sa.Boolean,
        nullable=False,
        server_default=expression.true(),
        doc="If true, it hides users.email",
    ),
    sa.Column(
        "hide_fullname",
        sa.Boolean,
        nullable=False,
        server_default=expression.true(),
        doc="If true, it hides users.first_name, users.last_name",
    ),
)

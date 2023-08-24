import sqlalchemy as sa

from .base import metadata
from .users import users

user_preferences = sa.Table(
    "user_preferences",
    metadata,
    sa.Column(
        "user_preference_name",
        sa.String,
        nullable=False,
        primary_key=True,
        doc="preference name which also includes the user_id",
    ),
    sa.Column(
        "user_id",
        sa.BigInteger,
        sa.ForeignKey(
            users.c.id,
            name="fk_user_preferences_id_users",
            ondelete="CASCADE",
            onupdate="CASCADE",
        ),
        nullable=False,
    ),
    sa.Column(
        "payload",
        sa.LargeBinary,
        nullable=False,
        doc="property content encoded as bytes",
    ),
)

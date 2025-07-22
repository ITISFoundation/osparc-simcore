import sqlalchemy as sa

from ._common import RefActions, column_modified_datetime
from .base import metadata

__all__: tuple[str, ...] = ("users_secrets",)

users_secrets = sa.Table(
    "users_secrets",
    metadata,
    #
    # User Secrets  ------------------
    #
    sa.Column(
        "user_id",
        sa.BigInteger(),
        sa.ForeignKey(
            "users.id",
            name="fk_users_secrets_user_id_users",
            onupdate=RefActions.CASCADE,
            ondelete=RefActions.CASCADE,
        ),
        nullable=False,
    ),
    sa.Column(
        "password_hash",
        sa.String(),
        nullable=False,
        doc="Hashed password",
    ),
    column_modified_datetime(timezone=True, doc="Last password modification timestamp"),
    # ---------------------------
    sa.PrimaryKeyConstraint("user_id", name="users_secrets_pkey"),
)

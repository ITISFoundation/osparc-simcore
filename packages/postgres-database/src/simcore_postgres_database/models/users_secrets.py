import sqlalchemy as sa

from ..utils_users_secrets import FALLBACK_PRODUCT_NAME
from ._common import RefActions, column_modified_datetime
from .base import metadata
from .products import products

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
        "product_name",
        sa.String,
        sa.ForeignKey(
            products.c.name,
            name="fk_users_secrets_product_name_products",
            onupdate=RefActions.CASCADE,
            ondelete=RefActions.CASCADE,
        ),
        nullable=False,
        doc="Product this password belongs to. Passwords are scoped per-product: if a user has no "
        f"password for a given product, it is copied over from the '{FALLBACK_PRODUCT_NAME}' product on first use.",
    ),
    sa.Column(
        "password_hash",
        sa.String(),
        nullable=False,
        doc="Hashed password",
    ),
    column_modified_datetime(timezone=True, doc="Last password modification timestamp"),
    # ---------------------------
    sa.PrimaryKeyConstraint("user_id", "product_name", name="users_secrets_pkey"),
)

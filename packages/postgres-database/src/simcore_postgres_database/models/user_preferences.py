import sqlalchemy as sa

from ._common import RefActions
from .base import metadata
from .products import products
from .users import users


def _user_id_column(fk_name: str) -> sa.Column:
    return sa.Column(
        "user_id",
        sa.BigInteger,
        sa.ForeignKey(
            users.c.id,
            name=fk_name,
            ondelete=RefActions.CASCADE,
            onupdate=RefActions.CASCADE,
        ),
        nullable=False,
    )


def _product_name_column(fk_name: str) -> sa.Column:
    return sa.Column(
        "product_name",
        sa.String,
        sa.ForeignKey(
            products.c.name,
            name=fk_name,
            ondelete=RefActions.CASCADE,
            onupdate=RefActions.CASCADE,
        ),
        nullable=False,
    )


def _preference_name_column() -> sa.Column:
    return sa.Column(
        "preference_name",
        sa.String,
        nullable=False,
    )


user_preferences_frontend = sa.Table(
    "user_preferences_frontend",
    metadata,
    _user_id_column("fk_user_preferences_frontend_id_users"),
    _product_name_column("fk_user_preferences_frontend_name_products"),
    _preference_name_column(),
    sa.Column(
        "payload",
        sa.JSON,
        nullable=False,
        doc="preference content encoded as json",
    ),
    sa.PrimaryKeyConstraint(
        "user_id",
        "product_name",
        "preference_name",
        name="user_preferences_frontend_pk",
    ),
)

user_preferences_user_service = sa.Table(
    "user_preferences_user_service",
    metadata,
    _user_id_column("fk_user_preferences_user_service_id_users"),
    _product_name_column("fk_user_preferences_user_service_name_products"),
    _preference_name_column(),
    sa.Column(
        "payload",
        sa.LargeBinary,
        nullable=False,
        doc="preference content encoded as bytes",
    ),
    sa.PrimaryKeyConstraint(
        "user_id",
        "product_name",
        "preference_name",
        name="user_preferences_user_service_pk",
    ),
)

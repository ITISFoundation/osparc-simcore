""" API keys to access public API


These keys grant the client authorization to the API resources

 +--------+                               +---------------+
 |        |--(A)- Authorization Request ->|   Resource    |
 |client  |                               |     Owner     | Authorization request
 |        |<-(B)-- Authorization Grant ---|               |
 +--------+                                +---------------+

"""
import sqlalchemy as sa
from sqlalchemy.sql import func

from ._common import RefActions
from .base import metadata
from .users import users

api_keys = sa.Table(
    "api_keys",
    metadata,
    sa.Column(
        "id",
        sa.BigInteger(),
        nullable=False,
        primary_key=True,
        doc="Primary key identifier",
    ),
    sa.Column(
        "display_name",
        sa.String(),
        nullable=False,
        doc="Human readable name. Unique for each user. SEE unique constraint below",
    ),
    sa.Column(
        "user_id",
        sa.BigInteger(),
        sa.ForeignKey(users.c.id, ondelete=RefActions.CASCADE),
        nullable=False,
        doc="Identified user",
    ),
    sa.Column(
        "product_name",
        sa.String,
        sa.ForeignKey(
            "products.name",
            onupdate=RefActions.CASCADE,
            ondelete=RefActions.CASCADE,
            name="fk_api_keys_product_name",
        ),
        nullable=False,
        doc="Identified product",
    ),
    sa.Column("api_key", sa.String(), nullable=False),
    sa.Column("api_secret", sa.String(), nullable=False),
    sa.Column(
        "created",
        sa.DateTime(),
        nullable=False,  # WARNING: still not updated to correct utc
        server_default=func.now(),
        doc="Timestamp auto-generated upon creation",
    ),
    sa.Column(
        "expires_at",
        sa.DateTime(),  # WARNING: still not updated to correct utc
        nullable=True,
        doc="Sets the expiration date for this api-key."
        "If set to NULL then the key does not expire.",
    ),
    sa.UniqueConstraint(
        "display_name", "user_id", name="display_name_userid_uniqueness"
    ),
)


#
# NOTE: Currently we scheduled a task that periodically prunes all rows that are expired
# This task is deployed in the GC service but it could als be done with a trigger in the
# postgres db itself. SEE draft idea (it would require some changes) in
# https://schinckel.net/2021/09/09/automatically-expire-rows-in-postgres/
#

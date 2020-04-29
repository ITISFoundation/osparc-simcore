""" API keys to access public gateway


These keys grant the client authorization to the API resources

 +--------+                               +---------------+
 |        |--(A)- Authorization Request ->|   Resource    |
 |client  |                               |     Owner     | Authorization request
 |        |<-(B)-- Authorization Grant ---|               |
 +--------+                                +---------------+

"""
import sqlalchemy as sa

from .base import metadata
from .users import users

api_keys = sa.Table(
    "api_keys",
    metadata,
    sa.Column("id", sa.BigInteger, nullable=False, primary_key=True),
    sa.Column("display_name", sa.String, nullable=False),
    sa.Column(
        "user_id",
        sa.BigInteger,
        sa.ForeignKey(users.c.id, ondelete="CASCADE"),
        nullable=False,
    ),
    sa.Column("api_key", sa.String, nullable=False),
    sa.Column("api_secret", sa.String, nullable=False),
    sa.UniqueConstraint(
        "display_name", "user_id", name="display_name_userid_uniqueness"
    ),
)

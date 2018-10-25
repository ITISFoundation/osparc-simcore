"""
    Object Relational Models
"""
# pylint: disable=E1101

import enum
from datetime import datetime

import sqlalchemy as sa

# ENUM TYPES ----------------------------------------------------------------

class UserStatus(enum.Enum):
    """
        pending: user registered but not confirmed
        active: user is authorized
        banned: user is not authorized
    """
    CONFIRMATION_PENDING = "pending"
    ACTIVE = "active"
    BANNED = "banned"

class UserRole(enum.IntEnum):
    """
        TODO: based on the user role, one can define pemissions
        to perform certain tasks

        anonymous: User who is not logged in. Read only access?
        user: basic permissions to use the platform [default]
        moderator: adds permissions ...???
        admin: full access
    """
    ANONYMOUS = 0
    USER = 1
    MODERATOR = 2
    ADMIN = 100


class ConfirmationAction(enum.Enum):
    REGISTRATION = "registration"
    RESET_PASSWORD = "reset_password"
    CHANGE_EMAIL = "change_email"


# TABLES ----------------------------------------------------------------
#
#  We use a classical Mapping w/o using a Declarative system.
#
# See https://docs.sqlalchemy.org/en/latest/orm/mapping_styles.html#classical-mappings

metadata = sa.MetaData()

users = sa.Table("users", metadata,
    sa.Column("id", sa.BigInteger, nullable=False),
    sa.Column("name", sa.String, nullable=False),
    sa.Column("email", sa.String, nullable=False),
    sa.Column("password_hash", sa.String, nullable=False),
    sa.Column("status",
        sa.Enum(UserStatus),
        nullable=False,
        default=UserStatus.CONFIRMATION_PENDING),
    sa.Column("role",
        sa.Enum(UserRole),
        nullable=False,
        default=UserRole.USER),
    sa.Column("created_at", sa.DateTime(), nullable=False, default=datetime.utcnow),
    sa.Column("created_ip", sa.String(), nullable=True),

    #
    sa.PrimaryKeyConstraint("id", name="user_pkey"),
    sa.UniqueConstraint("email", name="user_login_key"),
)


confirmations = sa.Table("confirmations", metadata,
    sa.Column("code", sa.Text),
    sa.Column("user_id", sa.BigInteger),
    sa.Column("action",
        sa.Enum(ConfirmationAction),
        nullable=False,
        default=ConfirmationAction.REGISTRATION
    ),
    sa.Column("data", sa.Text), # TODO: json?
    sa.Column("created_at", sa.DateTime, nullable=False),

    #
    sa.PrimaryKeyConstraint("code", name="confirmation_code"),
    sa.ForeignKeyConstraint(["user_id"], [users.c.id],
                            name="user_confirmation_fkey",
                            ondelete="CASCADE"),
 )


# NOTE: this is another way of of defining keys ...
tokens = sa.Table("tokens", metadata,
    sa.Column("token_id", sa.BigInteger, nullable=False, primary_key=True),
    sa.Column("user_id", sa.BigInteger, sa.ForeignKey(users.c.id), nullable=False),
    sa.Column("token_service", sa.String, nullable=False),
    sa.Column("token_data", sa.JSON, nullable=False),

)


# TODO: roles table that maps every role with allowed tasks e.g. read/write,...??

__all__ = (
    "UserStatus", "UserRole", "ConfirmationAction",
    "users", "confirmations", "tokens"
)

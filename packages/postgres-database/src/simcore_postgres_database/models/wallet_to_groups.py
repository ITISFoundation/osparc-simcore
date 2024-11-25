import sqlalchemy as sa
from sqlalchemy.sql import expression

from ._common import RefActions, column_created_datetime, column_modified_datetime
from .base import metadata
from .groups import groups
from .wallets import wallets

wallet_to_groups = sa.Table(
    "wallet_to_groups",
    metadata,
    sa.Column(
        "wallet_id",
        sa.BigInteger,
        sa.ForeignKey(
            wallets.c.wallet_id,
            name="fk_wallet_to_groups_id_wallets",
            onupdate=RefActions.CASCADE,
            ondelete=RefActions.CASCADE,
        ),
        doc="Wallet unique ID",
    ),
    sa.Column(
        "gid",
        sa.BigInteger,
        sa.ForeignKey(
            groups.c.gid,
            name="fk_wallet_to_groups_gid_groups",
            onupdate=RefActions.CASCADE,
            ondelete=RefActions.CASCADE,
        ),
        doc="Group unique IDentifier",
    ),
    # Access Rights flags ---
    sa.Column(
        "read",
        sa.Boolean,
        nullable=False,
        server_default=expression.false(),
        doc="If true, group can use the wallet",
    ),
    sa.Column(
        "write",
        sa.Boolean,
        nullable=False,
        server_default=expression.false(),
        doc="If true, group can modify the wallet",
    ),
    sa.Column(
        "delete",
        sa.Boolean,
        nullable=False,
        server_default=expression.false(),
        doc="If true, group can delete the wallet",
    ),
    # -----
    column_created_datetime(timezone=True),
    column_modified_datetime(timezone=True),
    sa.UniqueConstraint("wallet_id", "gid"),
)

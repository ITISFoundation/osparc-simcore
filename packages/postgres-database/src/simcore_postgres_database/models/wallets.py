import enum

import sqlalchemy as sa

from ._common import RefActions, column_created_datetime, column_modified_datetime
from .base import metadata


class WalletStatus(str, enum.Enum):
    ACTIVE = "ACTIVE"
    INACTIVE = "INACTIVE"


wallets = sa.Table(
    "wallets",
    metadata,
    sa.Column(
        "wallet_id",
        sa.BigInteger,
        nullable=False,
        autoincrement=True,
        primary_key=True,
        doc="Wallet index",
    ),
    sa.Column("name", sa.String, nullable=False, doc="Display name"),
    sa.Column("description", sa.String, nullable=True, doc="Short description"),
    sa.Column(
        "owner",
        sa.BigInteger,
        sa.ForeignKey(
            "groups.gid",
            name="fk_wallets_gid_groups",
            onupdate=RefActions.CASCADE,
            ondelete=RefActions.RESTRICT,
        ),
        nullable=False,
        doc="Identifier of the group that owns this wallet (Should be just PRIMARY GROUP)",
    ),
    sa.Column(
        "thumbnail",
        sa.String,
        nullable=True,
        doc="Link to image as to wallet thumbnail",
    ),
    sa.Column(
        "status",
        sa.Enum(WalletStatus),
        nullable=False,
        doc="Status of the wallet: ACTIVE or DEACTIVE",
    ),
    column_created_datetime(timezone=True),
    column_modified_datetime(timezone=True),
    sa.Column(
        "product_name",
        sa.String,
        sa.ForeignKey(
            "products.name",
            onupdate=RefActions.CASCADE,
            ondelete=RefActions.CASCADE,
            name="fk_wallets_product_name",
        ),
        nullable=False,
        doc="Products unique name",
    ),
)

# ------------------------ TRIGGERS
new_wallet_trigger = sa.DDL(
    """
DROP TRIGGER IF EXISTS wallet_modification on wallets;
CREATE TRIGGER wallet_modification
AFTER INSERT ON wallets
    FOR EACH ROW
    EXECUTE PROCEDURE set_wallet_to_owner_group();
"""
)


# --------------------------- PROCEDURES
assign_wallet_access_rights_to_owner_group_procedure = sa.DDL(
    """
CREATE OR REPLACE FUNCTION set_wallet_to_owner_group() RETURNS TRIGGER AS $$
DECLARE
    group_id BIGINT;
BEGIN
    IF TG_OP = 'INSERT' THEN
        INSERT INTO "wallet_to_groups" ("gid", "wallet_id", "read", "write", "delete") VALUES (NEW.owner, NEW.id, TRUE, TRUE, TRUE);
    END IF;
    RETURN NULL;
END; $$ LANGUAGE 'plpgsql';
    """
)

sa.event.listen(
    wallets, "after_create", assign_wallet_access_rights_to_owner_group_procedure
)
sa.event.listen(
    wallets,
    "after_create",
    new_wallet_trigger,
)

"""Licenses public facade per DESIGN.md §133-152."""

# Exceptions
# Functions
from ._itis_vip_service import get_category_items
from ._licensed_items_checkouts_service import (
    checkout_licensed_item_for_wallet,
    get_licensed_item_checkout,
    list_licensed_items_checkouts_for_wallet,
    release_licensed_item_for_wallet,
)
from ._licensed_items_purchases_service import (
    get_licensed_item_purchase,
    list_licensed_items_purchases,
)
from ._licensed_items_service import (
    get_licensed_item,
    list_licensed_items,
    purchase_licensed_item,
)
from ._licensed_resources_service import (
    register_licensed_resource,
    trash_licensed_resource,
    untrash_licensed_resource,
)

__all__: tuple[str, ...] = (
    # functions
    "checkout_licensed_item_for_wallet",
    "get_category_items",
    "get_licensed_item",
    "get_licensed_item_checkout",
    "get_licensed_item_purchase",
    "list_licensed_items",
    "list_licensed_items_checkouts_for_wallet",
    "list_licensed_items_purchases",
    "purchase_licensed_item",
    "register_licensed_resource",
    "release_licensed_item_for_wallet",
    "trash_licensed_resource",
    "untrash_licensed_resource",
)  # nopycln: file

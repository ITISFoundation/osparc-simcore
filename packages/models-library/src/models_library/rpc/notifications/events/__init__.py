from typing import TypeAlias

from ._account_events import (
    AccountApprovedEvent,
    AccountRejectedEvent,
    AccountRequestedEvent,
    ProductData,
    ProductUIData,
    UserData,
)

Event: TypeAlias = AccountRequestedEvent | AccountApprovedEvent | AccountRejectedEvent


__all__: tuple[str, ...] = (
    "AccountApprovedEvent",
    "AccountRejectedEvent",
    "AccountRequestedEvent",
    "Event",
    "ProductData",
    "ProductUIData",
    "UserData",
)

# nopycln: file

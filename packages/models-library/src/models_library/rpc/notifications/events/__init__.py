from typing import TypeAlias

from ._account_events import (
    AccountApprovedEvent,
    AccountRejectedEvent,
    AccountRequestedEvent,
)

Event: TypeAlias = AccountRequestedEvent | AccountApprovedEvent | AccountRejectedEvent


__all__: tuple[str, ...] = (
    "AccountApprovedEvent",
    "AccountRejectedEvent",
    "AccountRequestedEvent",
    "Event",
)

# nopycln: file

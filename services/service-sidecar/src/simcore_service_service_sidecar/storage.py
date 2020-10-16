from typing import Any


class Store:
    """Define custom storage abstraction for easy future extention"""

    KEY = "compose_spec"  # default key for all actions

    def __init__(self):
        self._storage = {}

    async def get(self, default=None) -> Any:
        return self._storage.get(Store.KEY, default)

    async def update(self, value: Any) -> None:
        self._storage[Store.KEY] = value


store = Store()

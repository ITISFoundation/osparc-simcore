from asyncio import Lock


class AsyncResourceLock:
    __slots__ = ("_lock", "_is_locked")

    def __init__(self, is_locked):
        self._lock = Lock()
        self._is_locked = is_locked

    def __str__(self) -> str:
        return f"<{self.__class__.__name__} _lock={self._lock}, _is_locked={self._is_locked}>"

    async def mark_as_locked_if_unlocked(self) -> bool:
        """
        If the resource is currently not in used it will mark it as in use.

        returns: True if it succeeds otherwise False
        """
        async with self._lock:
            if not self._is_locked:
                self._is_locked = True
                return True

        return False

    async def unlock_resource(self) -> None:
        """Marks the resource as unlocked"""
        async with self._lock:
            self._is_locked = False

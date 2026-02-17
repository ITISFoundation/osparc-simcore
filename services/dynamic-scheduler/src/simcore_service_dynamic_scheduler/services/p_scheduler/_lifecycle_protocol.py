from typing import Protocol


class SupportsLifecycle(Protocol):
    async def setup(self) -> None:
        """initialize resource or components"""

    async def shutdown(self) -> None:
        """clean resource or components"""

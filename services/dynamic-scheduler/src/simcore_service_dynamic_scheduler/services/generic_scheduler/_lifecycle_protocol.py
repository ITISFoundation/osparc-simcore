from typing import Protocol


class SupportsLifecycle(Protocol):
    async def setup(self) -> None:
        """initialize resource or compoennts"""

    async def shutdown(self) -> None:
        """clean resource or components"""

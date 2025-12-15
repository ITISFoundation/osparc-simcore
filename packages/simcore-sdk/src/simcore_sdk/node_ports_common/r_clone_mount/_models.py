from pathlib import Path
from typing import Protocol


class GetBindPathsProtocol(Protocol):
    async def __call__(self, state_path: Path) -> list: ...

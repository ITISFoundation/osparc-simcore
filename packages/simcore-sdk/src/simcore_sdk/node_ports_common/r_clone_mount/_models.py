from pathlib import Path
from typing import Protocol

from models_library.progress_bar import ProgressReport
from pydantic import BaseModel


class MountActivity(BaseModel):
    transferring: dict[str, ProgressReport]
    queued: list[str]


class GetBindPathsProtocol(Protocol):
    async def __call__(self, state_path: Path) -> list: ...


class MountActivityProtocol(Protocol):
    async def __call__(self, state_path: Path, activity: MountActivity) -> None: ...


class ShutdownHandlerProtocol(Protocol):
    async def __call__(self) -> None: ...

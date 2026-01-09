from pathlib import Path
from typing import Protocol

from models_library.progress_bar import ProgressReport
from pydantic import BaseModel

type MountId = str

type Transferring = dict[str, ProgressReport]


class MountActivity(BaseModel):
    transferring: Transferring
    queued: list[str]


class GetBindPathsProtocol(Protocol):
    async def __call__(self, state_path: Path) -> list: ...


class MountActivityProtocol(Protocol):
    async def __call__(self, state_path: Path, activity: MountActivity) -> None: ...


class RequestShutdownProtocol(Protocol):
    async def __call__(self) -> None: ...

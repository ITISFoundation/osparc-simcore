import logging
from dataclasses import dataclass, field
from types import TracebackType

from aiodocker.docker import Docker
from fastapi import FastAPI

_logger = logging.getLogger(__name__)


@dataclass
class VolumeManager:
    app: FastAPI
    docker: Docker = field(default_factory=Docker)

    async def close(self) -> None:
        await self.docker.close()

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None:
        await self.close()

    async def __aenter__(self) -> "VolumeManager":
        return self

    # TODO: this add book keeping task
    # TODO: add task that figures out when volumes are no longer used after x minutes
    # TODO: remove volumes which are no longer useed after x minutes
    # TODO: add a way to resolve volume removal actions via queues to avoid 2 users removing the same thing
    # TODO: not finishd with this still require smore


def get_volume_manager(app: FastAPI) -> VolumeManager:
    volume_manager: VolumeManager = app.state.volume_manager
    return volume_manager


def setup_volume_manager(app: FastAPI) -> None:
    async def _on_startup() -> None:
        app.state.volume_manager = VolumeManager(app)

    async def _on_shutdown() -> None:
        volume_manager: VolumeManager = app.state.volume_manager
        await volume_manager.close()

    app.add_event_handler("startup", _on_startup)
    app.add_event_handler("shutdown", _on_shutdown)

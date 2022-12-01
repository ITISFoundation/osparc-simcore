from dataclasses import dataclass, field
from pathlib import Path

import aioprocessing
from aioprocessing.queues import AioQueue
from fastapi import FastAPI

from ..mounted_fs import MountedVolumes


@dataclass
class OutputsContext:
    outputs_path: Path

    # _PortKeysEventHandler (generates) -> EventFilter (receives)
    port_key_events_queue: AioQueue = field(default_factory=aioprocessing.AioQueue)

    _port_keys: list[str] = field(default_factory=list)
    # OutputsContext (generates) -> _EventHandlerProcess(receives)
    port_keys_updates_queue: AioQueue = field(default_factory=aioprocessing.AioQueue)

    async def set_port_keys(self, port_keys: list[str]) -> None:
        self._port_keys = port_keys
        await self.port_keys_updates_queue.coro_put(  # pylint:disable=no-member
            self.port_keys
        )

    @property
    def port_keys(self) -> list[str]:
        return self._port_keys


def setup_outputs_context(app: FastAPI) -> None:
    async def on_startup() -> None:
        assert isinstance(app.state.mounted_volumes, MountedVolumes)  # nosec
        mounted_volumes: MountedVolumes = app.state.mounted_volumes

        app.state.outputs_context = OutputsContext(
            outputs_path=mounted_volumes.disk_outputs_path
        )

    app.add_event_handler("startup", on_startup)

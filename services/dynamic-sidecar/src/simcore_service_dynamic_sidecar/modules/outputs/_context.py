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

    # OutputsContext (generates) -> _EventHandlerProcess(receives)
    file_type_port_keys_updates_queue: AioQueue = field(
        default_factory=aioprocessing.AioQueue
    )

    # contains port types such as int, str, bool
    non_file_type_port_keys: list[str] = field(default_factory=list)

    # port types can contain one or more files and directories
    _file_type_port_keys: list[str] = field(default_factory=list)

    async def set_file_type_port_keys(self, file_type_port_keys: list[str]) -> None:
        self._file_type_port_keys = file_type_port_keys
        await self.file_type_port_keys_updates_queue.coro_put(  # pylint:disable=no-member
            self._file_type_port_keys
        )

    @property
    def file_type_port_keys(self) -> list[str]:
        return self._file_type_port_keys


def setup_outputs_context(app: FastAPI) -> None:
    async def on_startup() -> None:
        assert isinstance(app.state.mounted_volumes, MountedVolumes)  # nosec
        mounted_volumes: MountedVolumes = app.state.mounted_volumes

        app.state.outputs_context = OutputsContext(
            outputs_path=mounted_volumes.disk_outputs_path
        )

    app.add_event_handler("startup", on_startup)

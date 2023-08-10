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
    file_system_event_handler_queue: AioQueue = field(
        default_factory=aioprocessing.AioQueue
    )

    # contains port types such as int, str, bool
    non_file_type_port_keys: list[str] = field(default_factory=list)

    # port types can contain one or more files and directories
    _file_type_port_keys: list[str] = field(default_factory=list)

    async def set_file_type_port_keys(self, file_type_port_keys: list[str]) -> None:
        self._file_type_port_keys = file_type_port_keys
        await self.file_system_event_handler_queue.coro_put(  # pylint:disable=no-member
            {
                "method_name": "handle_set_outputs_port_keys",
                "kwargs": {"outputs_port_keys": self._file_type_port_keys},
            }
        )

    async def toggle_event_propagation(self, *, is_enabled: bool) -> None:
        await self.file_system_event_handler_queue.coro_put(  # pylint:disable=no-member
            {
                "method_name": "handle_toggle_event_propagation",
                "kwargs": {"is_enabled": is_enabled},
            }
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

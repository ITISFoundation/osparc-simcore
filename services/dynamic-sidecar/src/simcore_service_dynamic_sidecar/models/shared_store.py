from asyncio import Lock
from pathlib import Path
from typing import Final, TypeAlias

import aiofiles
from fastapi import FastAPI
from models_library.volumes import VolumeCategory, VolumeStatus
from pydantic import BaseModel, Field, PrivateAttr

from ..core.settings import ApplicationSettings
from .volumes import VolumeState

ContainerNameStr: TypeAlias = str

STORE_FILE_NAME: Final[str] = "data.json"


class _StoreMixin(BaseModel):
    _shared_store_dir: Path | None = PrivateAttr()
    _persist_lock: Lock | None = PrivateAttr()

    async def __aenter__(self) -> None:
        assert self._persist_lock  # nosec
        await self._persist_lock.acquire()
        return None

    async def __aexit__(self, *args) -> None:
        await self._persist_to_disk()

        assert self._persist_lock  # nosec
        self._persist_lock.release()

    async def _persist_to_disk(self) -> None:
        assert self._shared_store_dir  # nosec
        async with aiofiles.open(
            self._shared_store_dir / STORE_FILE_NAME, "w"
        ) as data_file:
            await data_file.write(self.json())


class SharedStore(_StoreMixin):
    """
    When used as a context manager will persist the state to the disk upon exit.

    NOTE: when updating the contents of the shared store always use a context manger
    to avoid concurrency issues.

    Example:
        async with shared_store:
            copied_list = deepcopy(shared_store.container_names)
            copied_list.append("a_container_name")
            shared_store.container_names = copied_list
    """

    compose_spec: str | None = Field(
        default=None, description="stores the stringified compose spec"
    )
    container_names: list[ContainerNameStr] = Field(
        default_factory=list,
        description="stores the container names from the compose_spec",
    )

    volume_states: dict[VolumeCategory, VolumeState] = Field(
        default_factory=dict, description="persist the state of each volume"
    )

    async def _setup_initial_volume_states(self) -> None:
        async with self:
            for category, status in [
                (VolumeCategory.INPUTS, VolumeStatus.CONTENT_NO_SAVE_REQUIRED),
                (VolumeCategory.SHARED_STORE, VolumeStatus.CONTENT_NO_SAVE_REQUIRED),
                (VolumeCategory.OUTPUTS, VolumeStatus.CONTENT_NEEDS_TO_BE_SAVED),
                (VolumeCategory.STATES, VolumeStatus.CONTENT_NEEDS_TO_BE_SAVED),
            ]:
                self.volume_states[category] = VolumeState(status=status)

    @classmethod
    async def init_from_disk(cls, shared_store_dir: Path) -> "SharedStore":
        def _init_private(obj: SharedStore):
            # pylint: disable=protected-access
            obj._shared_store_dir = shared_store_dir
            obj._persist_lock = Lock()

        data_file_path = shared_store_dir / STORE_FILE_NAME

        if not data_file_path.exists():
            obj = cls()
            _init_private(obj)
            await obj._setup_initial_volume_states()
            return obj

        # if the sidecar is started for a second time (usually the container dies)
        # it will load the previous data which was stored
        async with aiofiles.open(shared_store_dir / STORE_FILE_NAME) as data_file:
            file_content = await data_file.read()

        obj = cls.parse_obj(file_content)
        _init_private(obj)
        return obj


def setup_shared_store(app: FastAPI) -> None:
    async def on_startup() -> None:
        settings: ApplicationSettings = app.state.settings

        app.state.shared_store = await SharedStore.init_from_disk(
            settings.DYNAMIC_SIDECAR_SHARED_STORE_DIR
        )

    app.add_event_handler("startup", on_startup)

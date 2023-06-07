from asyncio import Lock
from pathlib import Path
from typing import TypeAlias

import aiofiles
from fastapi import FastAPI
from models_library.sidecar_volumes import VolumeCategory, VolumeState, VolumeStatus
from pydantic import BaseModel, Field, PrivateAttr
from servicelib.sidecar_volumes import STORE_FILE_NAME, VolumeUtils

from ..core.settings import ApplicationSettings

ContainerNameStr: TypeAlias = str


class _StoreMixin(BaseModel):
    _shared_store_dir: Path | None = PrivateAttr()
    _persist_lock: Lock = PrivateAttr(default_factory=Lock)

    async def __aenter__(self) -> None:
        await self._persist_lock.acquire()
        return None

    async def __aexit__(self, *args) -> None:
        await self._persist_to_disk()
        self._persist_lock.release()

    async def _persist_to_disk(self) -> None:
        assert self._shared_store_dir  # nosec
        async with aiofiles.open(
            self._shared_store_dir / STORE_FILE_NAME, "w"
        ) as data_file:
            await data_file.write(self.json())

    def post_init(self, shared_store_dir: Path):
        self._shared_store_dir = shared_store_dir


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

    async def _setup_initial_volume_states(self, settings: ApplicationSettings) -> None:
        initial_volumes_data: list[tuple[VolumeCategory, VolumeStatus, list[str]]] = [
            (
                VolumeCategory.INPUTS,
                VolumeStatus.CONTENT_NO_SAVE_REQUIRED,
                [
                    VolumeUtils.get_source(
                        path=settings.DY_SIDECAR_PATH_INPUTS,
                        node_uuid=settings.DY_SIDECAR_NODE_ID,
                        run_id=settings.DY_SIDECAR_RUN_ID,
                    )
                ],
            ),
            (
                VolumeCategory.SHARED_STORE,
                VolumeStatus.CONTENT_NO_SAVE_REQUIRED,
                [
                    VolumeUtils.get_source(
                        path=settings.DYNAMIC_SIDECAR_SHARED_STORE_DIR,
                        node_uuid=settings.DY_SIDECAR_NODE_ID,
                        run_id=settings.DY_SIDECAR_RUN_ID,
                    )
                ],
            ),
            (
                VolumeCategory.OUTPUTS,
                VolumeStatus.CONTENT_NEEDS_TO_BE_SAVED,
                [
                    VolumeUtils.get_source(
                        path=settings.DY_SIDECAR_PATH_OUTPUTS,
                        node_uuid=settings.DY_SIDECAR_NODE_ID,
                        run_id=settings.DY_SIDECAR_RUN_ID,
                    )
                ],
            ),
            (
                VolumeCategory.STATES,
                VolumeStatus.CONTENT_NEEDS_TO_BE_SAVED,
                [
                    VolumeUtils.get_source(
                        path=p,
                        node_uuid=settings.DY_SIDECAR_NODE_ID,
                        run_id=settings.DY_SIDECAR_RUN_ID,
                    )
                    for p in settings.DY_SIDECAR_STATE_PATHS
                ],
            ),
        ]
        async with self:
            for category, status, volume_names in initial_volumes_data:
                self.volume_states[category] = VolumeState(
                    status=status, volume_names=volume_names
                )

    @classmethod
    async def init_from_disk(cls, settings: ApplicationSettings) -> "SharedStore":
        shared_store_dir: Path = settings.DYNAMIC_SIDECAR_SHARED_STORE_DIR
        data_file_path = shared_store_dir / STORE_FILE_NAME

        if not data_file_path.exists():
            obj = cls()
            obj.post_init(shared_store_dir)
            await obj._setup_initial_volume_states(settings)
            return obj

        # if the sidecar is started for a second time (usually the container dies)
        # it will load the previous data which was stored
        async with aiofiles.open(shared_store_dir / STORE_FILE_NAME) as data_file:
            file_content = await data_file.read()

        obj = cls.parse_obj(file_content)
        obj.post_init(shared_store_dir)
        return obj


def setup_shared_store(app: FastAPI) -> None:
    async def on_startup() -> None:
        settings: ApplicationSettings = app.state.settings
        app.state.shared_store = await SharedStore.init_from_disk(settings)

    app.add_event_handler("startup", on_startup)

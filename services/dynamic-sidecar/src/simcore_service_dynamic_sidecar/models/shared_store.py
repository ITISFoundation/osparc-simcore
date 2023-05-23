from asyncio import Lock
from pathlib import Path
from typing import Final

import aiofiles
from fastapi import FastAPI
from pydantic import BaseModel, Field, PrivateAttr

from ..core.settings import ApplicationSettings

ContainerNameStr = str

STORE_FILE_NAME: Final[str] = "data.json"


# TODO: Objects with volume state and volume status that stores the information


class SharedStore(BaseModel):
    """
    When used as a context manager will persist the state to the disk upon exit.
    """

    _shared_store_dir: Path | None = PrivateAttr()
    _persist_lock: Lock | None = PrivateAttr()

    compose_spec: str | None = Field(
        default=None, description="stores the stringified compose spec"
    )
    container_names: list[ContainerNameStr] = Field(
        default_factory=list,
        description="stores the container names from the compose_spec",
    )

    async def __aenter__(self) -> None:
        return None

    async def __aexit__(self, *args) -> None:
        await self._persist_to_disk()

    def post_init(self, shared_store_dir: Path) -> None:
        self._shared_store_dir = shared_store_dir
        self._persist_lock = Lock()

    @classmethod
    async def init_from_disk(cls, shared_store_dir: Path) -> "SharedStore":
        data_file_path = shared_store_dir / STORE_FILE_NAME
        if data_file_path.exists():
            # if the sidecar is started for a second time (usually the container dies)
            # it will load the previous data which was stored
            async with aiofiles.open(shared_store_dir / STORE_FILE_NAME) as data_file:
                file_content = await data_file.read()

            obj = cls.parse_obj(file_content)
        else:
            obj = cls()

        obj.post_init(shared_store_dir)
        return obj

    async def _persist_to_disk(self) -> None:
        # NOTE: avoids having 2 persist operations running at the same time
        # creating partially saved data or out of date data

        assert self._persist_lock  # nosec
        assert self._shared_store_dir  # nosec

        async with self._persist_lock:
            async with aiofiles.open(
                self._shared_store_dir / STORE_FILE_NAME, "w"
            ) as data_file:
                await data_file.write(self.json())


def setup_shared_store(app: FastAPI) -> None:
    async def on_startup() -> None:
        settings: ApplicationSettings = app.state.settings

        app.state.shared_store = await SharedStore.init_from_disk(
            settings.DYNAMIC_SIDECAR_SHARED_STORE_DIR
        )

    app.add_event_handler("startup", on_startup)

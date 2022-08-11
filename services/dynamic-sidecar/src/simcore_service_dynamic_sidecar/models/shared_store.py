from pathlib import Path
from typing import Final, Optional

import aiofiles
from fastapi import FastAPI
from pydantic import BaseModel, Field, PrivateAttr

from ..core.settings import ApplicationSettings

ContainerNameStr = str

STORE_FILE_NAME: Final[str] = "data.json"


class SharedStore(BaseModel):
    _shared_store_dir: Path = PrivateAttr()

    compose_spec: Optional[str] = Field(
        default=None, description="stores the stringified compose spec"
    )
    container_names: list[ContainerNameStr] = Field(
        default_factory=list,
        description="stores the container names from the compose_spec",
    )

    async def clear(self):
        self.compose_spec = None
        self.container_names = []
        await self.persist_to_disk()

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

        obj._shared_store_dir = shared_store_dir  # pylint: disable=protected-access
        return obj

    async def persist_to_disk(self) -> None:
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

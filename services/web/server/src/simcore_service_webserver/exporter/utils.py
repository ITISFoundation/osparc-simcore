import asyncio
from collections.abc import Callable, Coroutine
from pathlib import Path
from typing import Any

from aiohttp.abc import AbstractStreamWriter
from aiohttp.typedefs import LooseHeaders
from aiohttp.web import BaseRequest, FileResponse


class CleanupFileResponse(FileResponse):  # pylint: disable=too-many-ancestors
    """
    After the FileResponse finishes a callback to remove the
    tmp directory where the export data was stored is scheduled and ran.
    """

    def __init__(
        self,
        remove_tmp_dir_cb: Callable[[], Coroutine[Any, Any, None]],
        path: str | Path,
        chunk_size: int = 256 * 1024,
        status: int = 200,
        reason: str | None = None,
        headers: LooseHeaders | None = None,
    ) -> None:
        super().__init__(
            path=path,
            chunk_size=chunk_size,
            status=status,
            # Multiline not allowed in HTTP reason
            reason=reason.replace("\n", " ") if reason else None,
            headers=headers,
        )
        self.remove_tmp_dir_cb = remove_tmp_dir_cb
        self.path = path

    async def prepare(self, request: BaseRequest) -> AbstractStreamWriter | None:
        try:
            return await super().prepare(request=request)
        finally:
            await asyncio.get_event_loop().create_task(
                self.remove_tmp_dir_cb(), name=f"remove tmp dir {self.path=}"
            )

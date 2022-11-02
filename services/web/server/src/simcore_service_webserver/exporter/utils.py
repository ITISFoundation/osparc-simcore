import asyncio
import os
from pathlib import Path
from typing import Any, Callable, Coroutine, Optional, Union

from aiofiles import os as aiofiles_os
from aiohttp.abc import AbstractStreamWriter
from aiohttp.typedefs import LooseHeaders
from aiohttp.web import FileResponse

makedirs = aiofiles_os.wrap(os.makedirs)  # as in aiofiles.os.py module
rename = aiofiles_os.wrap(os.rename)  # as in aiofiles.os.py module
path_getsize = aiofiles_os.wrap(os.path.getsize)  # as in aiofiles.os.py module


class CleanupFileResponse(FileResponse):  # pylint: disable=too-many-ancestors
    """
    After the FileResponse finishes a callback to remove the
    tmp directory where the export data was stored is scheduled and ran.
    """

    def __init__(
        self,
        remove_tmp_dir_cb: Callable[[], Coroutine[Any, Any, None]],
        path: Union[str, Path],
        chunk_size: int = 256 * 1024,
        status: int = 200,
        reason: Optional[str] = None,
        headers: Optional[LooseHeaders] = None,
    ) -> None:
        super().__init__(
            path=path,
            chunk_size=chunk_size,
            status=status,
            reason=reason,
            headers=headers,
        )
        self.remove_tmp_dir_cb = remove_tmp_dir_cb
        self.path = path

    async def prepare(self, request: "BaseRequest") -> Optional[AbstractStreamWriter]:
        try:
            return await super().prepare(request=request)
        finally:
            await asyncio.get_event_loop().create_task(
                self.remove_tmp_dir_cb(), name=f"remove tmp dir {self.path=}"
            )

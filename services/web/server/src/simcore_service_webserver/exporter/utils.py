import asyncio
import os
import tempfile
from pathlib import Path
from typing import Optional, Union

from aiofiles import os as aiofiles_os
from aiohttp.abc import AbstractStreamWriter
from aiohttp.typedefs import LooseHeaders
from aiohttp.web import FileResponse

makedirs = aiofiles_os.wrap(os.makedirs)  # as in aiofiles.os.py module
rename = aiofiles_os.wrap(os.rename)  # as in aiofiles.os.py module
path_getsize = aiofiles_os.wrap(os.path.getsize)  # as in aiofiles.os.py module


def _candidate_tmp_dir() -> Path:
    # pylint: disable=protected-access
    # let us all thank codeclimate for this beautiful piece of code
    return Path("/") / f"tmp/{next(tempfile._get_candidate_names())}"


async def get_empty_tmp_dir() -> str:
    candidate = _candidate_tmp_dir()
    while candidate.is_dir() or candidate.is_file() or candidate.is_symlink():
        candidate = _candidate_tmp_dir()

    await makedirs(candidate, exist_ok=True)

    return str(candidate)


async def remove_dir(directory: str) -> None:
    await asyncio.create_subprocess_exec("rm", "-rf", directory)


class CleanupFileResponse(FileResponse):  # pylint: disable=too-many-ancestors
    """
    After the FileResponse finishes a callback to remove the
    tmp directory where the export data was stored is scheduled and ran.
    """

    def __init__(
        self,
        temp_dir: str,
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
        self._temp_dir = temp_dir

    async def prepare(self, request: "BaseRequest") -> Optional[AbstractStreamWriter]:
        try:
            return await super().prepare(request=request)
        finally:
            await asyncio.get_event_loop().create_task(
                remove_dir(self._temp_dir), name=f"remove dir {self._temp_dir}"
            )

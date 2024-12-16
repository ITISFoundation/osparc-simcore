import asyncio
import logging
import re
from pathlib import Path

from models_library.basic_types import IDStr
from servicelib.progress_bar import ProgressBarData

from ..core.errors import SevenZipError
from ..core.utils import async_command

_logger = logging.getLogger(__name__)


async def _get_file_count(zip_path: Path) -> int:
    result = await async_command(f"7z l {zip_path}")
    if not result.success:
        raise SevenZipError(command=result.command, command_result=result.message)

    match = re.search(r"\s*(\d+)\s*files", result.message)
    return int(match.group().replace("files", "").strip())


async def unarchive_zip_to(
    zip_path: Path,
    output_dir: Path,
    progress_bar: ProgressBarData | None = None,
) -> set[Path]:
    if not progress_bar:
        progress_bar = ProgressBarData(
            num_steps=1, description=IDStr(f"extracting {zip_path.name}")
        )

    file_count = await _get_file_count(zip_path)

    command = f"7z x {zip_path} -o{output_dir} -bb1"
    process = await asyncio.create_subprocess_shell(
        command, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
    )

    async with progress_bar.sub_progress(
        steps=file_count, description=IDStr("...")
    ) as sub_prog:

        while True:
            line = await process.stdout.readline()
            if not line:
                break

            line_decoded = line.decode().strip()
            if line_decoded.startswith("- "):  # check file entry
                await sub_prog.update(1)

        await process.wait()
        if process.returncode != 0:
            stderr = await process.stderr.read()
            raise SevenZipError(command=command, command_result=stderr.decode().strip())

    return {x for x in output_dir.rglob("*") if x.is_file()}

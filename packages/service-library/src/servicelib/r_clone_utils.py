import asyncio
from typing import Final

from aiocache import cached  # type: ignore[import-untyped]
from common_library.errors_classes import OsparcErrorMixin
from pydantic import PositiveInt

_MINIMUM_R_CLONE_VERSION_PARTS: Final[PositiveInt] = 2


class _BaseRCloneError(OsparcErrorMixin, RuntimeError):
    pass


class RCloneCommandFailedError(_BaseRCloneError):
    msg_template = "Failed to get rclone version (exit code {exit_code}): {stderr_text}"


class RCloneEmptyOutputError(_BaseRCloneError):
    msg_template = "Failed to get rclone version: empty output from 'rclone --version'"


class RCloneVersionParseError(_BaseRCloneError):
    msg_template = "Failed to parse rclone version from output first line: {first_line!r}"


@cached()
async def get_r_clone_version() -> str:
    proc = await asyncio.create_subprocess_exec(
        "rclone",
        "--version",
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, stderr = await proc.communicate()

    if proc.returncode != 0:
        stderr_text = stderr.decode(errors="replace").strip()
        raise RCloneCommandFailedError(exit_code=proc.returncode, stderr_text=stderr_text)

    stdout_text = stdout.decode(errors="replace").strip()
    if not stdout_text:
        raise RCloneEmptyOutputError

    first_line = stdout_text.splitlines()[0].strip()
    parts = first_line.split()
    if len(parts) < _MINIMUM_R_CLONE_VERSION_PARTS:
        raise RCloneVersionParseError(first_line=first_line)

    version_part = parts[1]
    assert version_part.startswith("v")  # nosec
    return version_part.lstrip("v")

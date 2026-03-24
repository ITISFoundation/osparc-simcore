import asyncio

from aiocache import cached  # type: ignore[import-untyped]


@cached()
async def get_r_clone_version() -> str:
    proc = await asyncio.create_subprocess_exec(
        "rclone",
        "--version",
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, _ = await proc.communicate()
    first_line = stdout.decode().split("\n")[0]
    return first_line.split()[1].lstrip("v")

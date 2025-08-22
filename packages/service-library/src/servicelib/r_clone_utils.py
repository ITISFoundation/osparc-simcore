from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from aiofiles import tempfile


@asynccontextmanager
async def config_file(config: str) -> AsyncIterator[str]:
    async with tempfile.NamedTemporaryFile("w") as f:
        await f.write(config)
        await f.flush()
        assert isinstance(f.name, str)  # nosec
        yield f.name

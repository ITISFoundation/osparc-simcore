from pathlib import Path

from aiohttp import ClientSession
from simcore_service_storage.utils import MAX_CHUNK_SIZE, download_to_file_or_raise


async def test_download_files(tmpdir):

    destination = Path(tmpdir) / "data"
    expected_size = MAX_CHUNK_SIZE * 3 + 1000

    async with ClientSession() as session:
        total_size = await download_to_file_or_raise(
            session, f"https://httpbin.org/bytes/{expected_size}", destination
        )
        assert destination.exists()
        assert expected_size == total_size
        assert destination.stat().st_size == total_size

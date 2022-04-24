import asyncio
import logging
import re
import urllib.parse
from contextlib import asynccontextmanager
from pathlib import Path
from typing import AsyncGenerator, Optional

from aiofiles import tempfile
from aiohttp import ClientSession, ClientTimeout, web
from cache import AsyncLRU
from settings_library.r_clone import RCloneSettings
from settings_library.utils_r_clone import get_r_clone_config

from ..node_ports_common.filemanager import ETag

logger = logging.getLogger(__name__)


class _CommandFailedException(Exception):
    pass


class RCloneError(Exception):
    pass


@asynccontextmanager
async def _config_file(config: str) -> AsyncGenerator[str, None]:
    async with tempfile.NamedTemporaryFile("w") as f:
        await f.write(config)
        await f.flush()
        yield f.name


async def _async_command(command: str, *, cwd: Optional[str] = None) -> str:
    proc = await asyncio.create_subprocess_shell(
        command,
        stdin=asyncio.subprocess.PIPE,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.STDOUT,
        cwd=cwd,
    )

    stdout, _ = await proc.communicate()
    decoded_stdout = stdout.decode()
    if proc.returncode != 0:
        raise _CommandFailedException(
            f"Command {command} finished with exception:\n{decoded_stdout}"
        )

    logger.debug("'%s' result:\n%s", command, decoded_stdout)
    return decoded_stdout


@AsyncLRU(maxsize=2)
async def is_r_clone_available(r_clone_settings: Optional[RCloneSettings]) -> bool:
    """returns: True if the `rclone` cli is installed and a configuration is provided"""
    try:
        await _async_command("rclone --version")
        return r_clone_settings is not None
    except _CommandFailedException:
        return False


@asynccontextmanager
async def _get_client_session(
    r_clone_settings: RCloneSettings,
) -> AsyncGenerator[ClientSession, None]:
    client_timeout = ClientTimeout(
        total=r_clone_settings.R_CLONE_AIOHTTP_CLIENT_TIMEOUT_TOTAL,
        sock_connect=r_clone_settings.R_CLONE_AIOHTTP_CLIENT_TIMEOUT_SOCK_CONNECT,
    )  # type: ignore

    async with ClientSession(timeout=client_timeout) as session:
        yield session


async def _get_s3_link(
    r_clone_settings: RCloneSettings, s3_object: str, user_id: int
) -> str:
    async with _get_client_session(r_clone_settings) as session:
        url = "{endpoint}/v0/locations/0/files/{s3_object}/s3/link".format(
            endpoint=r_clone_settings.storage_endpoint,
            s3_object=urllib.parse.quote_plus(s3_object),
        )
        logger.debug("%s", f"{url=}")
        result = await session.get(url, params=dict(user_id=user_id))

        if result.status == web.HTTPForbidden.status_code:
            raise RCloneError(
                (
                    f"Insufficient permissions to upload {s3_object=} for {user_id=}. "
                    f"Storage: {await result.text()}"
                )
            )

        if result.status != web.HTTPOk.status_code:
            raise RCloneError(
                f"Could not fetch s3_link: status={result.status} {await result.text()}"
            )

        response = await result.json()
        return response["data"]["s3_link"]


async def _update_file_meta_data(
    r_clone_settings: RCloneSettings, s3_object: str
) -> ETag:
    async with _get_client_session(r_clone_settings) as session:
        url = "{endpoint}/v0/locations/0/files/{s3_object}/metadata".format(
            endpoint=r_clone_settings.storage_endpoint,
            s3_object=urllib.parse.quote_plus(s3_object),
        )
        logger.debug("%s", f"{url=}")
        result = await session.patch(url)
        if result.status != web.HTTPOk.status_code:
            raise RCloneError(
                f"Could not fetch metadata: status={result.status} {await result.text()}"
            )

        response = await result.json()
        logger.debug("metadata response %s", response)
        return response["data"]["entity_tag"]


async def _delete_file_meta_data(
    r_clone_settings: RCloneSettings, s3_object: str, user_id: int
) -> None:
    async with _get_client_session(r_clone_settings) as session:
        url = "{endpoint}/v0/locations/0/files/{s3_object}/metadata".format(
            endpoint=r_clone_settings.storage_endpoint,
            s3_object=urllib.parse.quote_plus(s3_object),
        )
        logger.debug("%s", f"{url=}")
        result = await session.delete(url, params=dict(user_id=user_id))
        if result.status != web.HTTPOk.status_code:
            raise RCloneError(
                f"Could not fetch metadata: status={result.status} {await result.text()}"
            )


async def sync_local_to_s3(
    r_clone_settings: Optional[RCloneSettings],
    s3_object: str,
    local_file_path: Path,
    user_id: int,
) -> ETag:
    if r_clone_settings is None:
        raise RCloneError(
            (
                f"Could not sync {local_file_path=} to {s3_object=}, provided "
                f"config is invalid{r_clone_settings=}"
            )
        )

    s3_link = await _get_s3_link(
        r_clone_settings=r_clone_settings, s3_object=s3_object, user_id=user_id
    )
    s3_path = re.sub(r"^s3://", "", s3_link)
    logger.debug(" %s; %s", f"{s3_link=}", f"{s3_path=}")

    r_clone_config_file_content = get_r_clone_config(r_clone_settings)
    async with _config_file(r_clone_config_file_content) as config_file_name:
        source_path = local_file_path
        destination_path = Path(s3_path)
        assert local_file_path.name == destination_path.name
        file_name = local_file_path.name

        # rclone only acts upon directories, so to target a specific file
        # we must run the command from the file's directory. See below
        # example for further details:
        #
        # local_file_path=`/tmp/pytest-of-silenthk/pytest-80/test_sync_local_to_s30/filee3e70682-c209-4cac-a29f-6fbed82c07cd.txt`
        # s3_path=`simcore/00000000-0000-0000-0000-000000000001/00000000-0000-0000-0000-000000000002/filee3e70682-c209-4cac-a29f-6fbed82c07cd.txt`
        #
        # rclone
        #   --config
        #   /tmp/tmpd_1rtmss
        #   sync
        #   '/tmp/pytest-of-silenthk/pytest-80/test_sync_local_to_s30'
        #   'dst:simcore/00000000-0000-0000-0000-000000000001/00000000-0000-0000-0000-000000000002'
        #   --progress
        #   --copy-links
        #   --include
        #   'filee3e70682-c209-4cac-a29f-6fbed82c07cd.txt'
        r_clone_command = [
            "rclone",
            "--config",
            config_file_name,
            "sync",
            f"'{source_path.parent}'",
            f"'dst:{destination_path.parent}'",
            "--progress",
            "--copy-links",
            "--include",
            f"'{file_name}'",
        ]

        try:
            await _async_command(" ".join(r_clone_command), cwd=f"{source_path.parent}")
            return await _update_file_meta_data(
                r_clone_settings=r_clone_settings, s3_object=s3_object
            )
        except Exception as e:
            logger.warning(
                "There was an error while uploading %s. Removing metadata", s3_object
            )
            await _delete_file_meta_data(
                r_clone_settings=r_clone_settings, s3_object=s3_object, user_id=user_id
            )
            raise e

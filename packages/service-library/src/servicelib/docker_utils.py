import logging
from collections.abc import Awaitable, Callable
from datetime import datetime

import aiodocker
import aiohttp
import arrow
from models_library.docker import DockerGenericTag
from servicelib.logging_utils import LogLevelInt
from servicelib.progress_bar import ProgressBarData
from settings_library.docker_registry import RegistrySettings
from yarl import URL


def to_datetime(docker_timestamp: str) -> datetime:
    # docker follows RFC3339Nano timestamp which is based on ISO 8601
    # https://medium.easyread.co/understanding-about-rfc-3339-for-datetime-formatting-in-software-engineering-940aa5d5f68a
    # This is acceptable in ISO 8601 and RFC 3339 (with T)
    # 2019-10-12T07:20:50.52Z
    # This is only accepted in RFC 3339 (without T)
    # 2019-10-12 07:20:50.52Z
    dt: datetime = arrow.get(docker_timestamp).datetime
    return dt


LogCB = Callable[[str, LogLevelInt], Awaitable[None]]


async def retrieve_image_layer_information(
    image: DockerGenericTag, registry_settings: RegistrySettings
):
    async with aiohttp.ClientSession() as session:
        # Setup the headers and auth for the request
        headers = {"Accept": "application/vnd.docker.distribution.manifest.v2+json"}
        auth = aiohttp.BasicAuth(
            login=registry_settings.REGISTRY_USER,
            password=registry_settings.REGISTRY_PW.get_secret_value(),
        )

        # Make the GET request
        image_url = URL(f"https://{image}")
        full_image_name = image_url.path.split(":")[0].strip("/")
        image_tag = image_url.name.split(":")[-1]
        manifest_url = image_url.with_path(
            f"v2/{full_image_name}/manifests/{image_tag}"
        )
        async with session.get(manifest_url, headers=headers, auth=auth) as response:
            # Check if the request was successful
            if response.status == 200:
                # Parse JSON response body if needed
                data = await response.json()
                return data
            else:
                # Handle error (you can also raise an HTTP error here)
                print(f"HTTP Error: {response.status}")
                return None


async def pull_image(
    image: DockerGenericTag,
    registry_settings: RegistrySettings,
    progress_bar: ProgressBarData,
    log_cb: LogCB,
) -> None:
    image_url = URL(f"https://{image}")
    assert image_url.host  # nosec
    registry_auth = None
    if bool(image_url.port or "." in image_url.host):
        registry_auth = {
            "username": registry_settings.REGISTRY_USER,
            "password": registry_settings.REGISTRY_PW.get_secret_value(),
        }
    async with aiodocker.Docker() as client:
        async for pull_progress in client.images.pull(
            image, stream=True, auth=registry_auth
        ):
            await log_cb(f"pulling {image_url.name}: {pull_progress}...", logging.DEBUG)

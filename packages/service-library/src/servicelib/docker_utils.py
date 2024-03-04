import logging
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import datetime
from typing import Literal

import aiodocker
import arrow
from models_library.docker import DockerGenericTag
from models_library.generated_models.docker_rest_api import ProgressDetail
from models_library.utils.change_case import snake_to_camel
from pydantic import BaseModel, ByteSize, parse_obj_as
from settings_library.docker_registry import RegistrySettings

from .logging_utils import LogLevelInt
from .progress_bar import ProgressBarData

_logger = logging.getLogger(__name__)


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


class DockerLayerSizeV2(BaseModel):
    media_type: str
    size: ByteSize
    digest: str

    class Config:
        frozen = True
        alias_generator = snake_to_camel


class DockerImageManifestsV2(BaseModel):
    schema_version: Literal[2]
    media_type: str
    config: DockerLayerSizeV2
    layers: list[DockerLayerSizeV2]

    class Config:
        frozen = True
        alias_generator = snake_to_camel


class _DockerPullImage(BaseModel):
    status: str
    id: str | None  # noqa: A003
    progress_detail: ProgressDetail | None
    progress: str | None

    class Config:
        frozen = True
        alias_generator = snake_to_camel


async def pull_image(
    image: DockerGenericTag,
    registry_settings: RegistrySettings,
    progress_bar: ProgressBarData,
    log_cb: LogCB,
    image_information: DockerImageManifestsV2,
) -> None:
    registry_auth = None
    if registry_settings.REGISTRY_URL in image:
        registry_auth = {
            "username": registry_settings.REGISTRY_USER,
            "password": registry_settings.REGISTRY_PW.get_secret_value(),
        }

    # NOTE: docker pulls an image layer by layer
    # NOTE: each layer is first downloaded, then extracted. Extraction usually takes about 2/3 of the time
    # NOTE: 1 subprogress per layer, then subprogress of size 2 with weights?
    # NOTE: or, we compute the total size X2, then upgrade that based on the status? maybe simpler

    @dataclass
    class PulledStatus:
        size: int
        downloaded: int = 0
        extracted: int = 0

    layer_id_to_size = {
        layer.digest.removeprefix("sha256:")[:12]: PulledStatus(layer.size)
        for layer in image_information.layers
    }
    image_layers_total_size = sum(layer.size for layer in image_information.layers) * 2
    iamge_name = image.split("/")[-1]
    async with (
        aiodocker.Docker() as client,
        progress_bar.sub_progress(image_layers_total_size) as sub_progress,
    ):
        async for pull_progress in client.images.pull(
            image, stream=True, auth=registry_auth
        ):
            parsed_progress = parse_obj_as(_DockerPullImage, pull_progress)
            match parsed_progress.status.lower():
                case progress_status if any(
                    msg in progress_status
                    for msg in [
                        "pulling from",
                        "pulling fs layer",
                        "waiting",
                        "digest: ",
                        "status: downloaded newer image for ",
                        "status: image is up to date for ",
                    ]
                ):
                    # nothing to do here
                    pass
                case "downloading":
                    assert parsed_progress.id  # nosec
                    assert parsed_progress.progress_detail  # nosec
                    assert parsed_progress.progress_detail.current  # nosec
                    layer_id_to_size[
                        parsed_progress.id
                    ].downloaded = parsed_progress.progress_detail.current
                case "verifying checksum" | "download complete":
                    assert parsed_progress.id  # nosec
                    layer_id_to_size[parsed_progress.id].downloaded = layer_id_to_size[
                        parsed_progress.id
                    ].size
                case "extracting":
                    assert parsed_progress.id  # nosec
                    assert parsed_progress.progress_detail  # nosec
                    assert parsed_progress.progress_detail.current  # nosec
                    layer_id_to_size[
                        parsed_progress.id
                    ].extracted = parsed_progress.progress_detail.current
                case "pull complete":
                    assert parsed_progress.id  # nosec
                    layer_id_to_size[parsed_progress.id].extracted = layer_id_to_size[
                        parsed_progress.id
                    ].size
                case _:
                    _logger.warning(
                        "unknown pull state: %s. Please check", parsed_progress
                    )

            # compute total progress
            total_downloaded_size = sum(
                layer.downloaded for layer in layer_id_to_size.values()
            )
            total_extracted_size = sum(
                layer.extracted for layer in layer_id_to_size.values()
            )
            await sub_progress.set_(total_downloaded_size + total_extracted_size)
            await log_cb(
                f"pulling {iamge_name}: {pull_progress}...",
                logging.DEBUG,
            )

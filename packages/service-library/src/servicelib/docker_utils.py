import logging
from collections.abc import Awaitable, Callable
from contextlib import AsyncExitStack
from dataclasses import dataclass
from datetime import datetime
from functools import cached_property
from typing import Any, Final, Literal

import aiodocker
import arrow
from models_library.docker import DockerGenericTag
from models_library.generated_models.docker_rest_api import ProgressDetail
from models_library.utils.change_case import snake_to_camel
from pydantic import BaseModel, ByteSize, ConfigDict, TypeAdapter, ValidationError
from settings_library.docker_registry import RegistrySettings
from yarl import URL

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
    model_config = ConfigDict(
        frozen=True,
        alias_generator=snake_to_camel,
        populate_by_name=True,
    )


class DockerImageManifestsV2(BaseModel):
    schema_version: Literal[2]
    media_type: str
    config: DockerLayerSizeV2
    layers: list[DockerLayerSizeV2]
    model_config = ConfigDict(
        ignored_types=(cached_property,),
        frozen=True,
        alias_generator=snake_to_camel,
        populate_by_name=True,
    )

    @cached_property
    def layers_total_size(self) -> ByteSize:
        return TypeAdapter(ByteSize).validate_python(
            sum(layer.size for layer in self.layers)
        )


class DockerImageMultiArchManifestsV2(BaseModel):
    schema_version: Literal[2]
    media_type: Literal["application/vnd.oci.image.index.v1+json"]
    manifests: list[dict[str, Any]]
    model_config = ConfigDict(
        frozen=True,
        alias_generator=snake_to_camel,
        populate_by_name=True,
    )


class _DockerPullImage(BaseModel):
    status: str
    id: str | None = None
    progress_detail: ProgressDetail | None = None
    progress: str | None = None
    model_config = ConfigDict(
        frozen=True,
        alias_generator=snake_to_camel,
        populate_by_name=True,
    )


DOCKER_HUB_HOST: Final[str] = "registry-1.docker.io"


def _create_docker_hub_complete_url(image: DockerGenericTag) -> URL:
    if len(image.split("/")) == 1:
        # official image, add library
        return URL(f"https://{DOCKER_HUB_HOST}/library/{image}")
    return URL(f"https://{DOCKER_HUB_HOST}/{image}")


def get_image_complete_url(
    image: DockerGenericTag, registry_settings: RegistrySettings
) -> URL:
    if registry_settings.REGISTRY_URL and registry_settings.REGISTRY_URL in image:
        # this is an image available in the private registry
        return URL(f"http{'s' if registry_settings.REGISTRY_AUTH else ''}://{image}")

    # this is an external image, like nginx:latest or library/nginx:latest or quay.io/stuff, ... -> https
    try:
        # NOTE: entries like nginx:latest or ngingx:1.3 will raise an exception here
        url = URL(f"https://{image}")
        assert url.host  # nosec
        if not url.port or "." not in url.host:
            # this is Dockerhub + official images are in /library
            url = _create_docker_hub_complete_url(image)
    except ValueError:
        # this is Dockerhub with missing host
        url = _create_docker_hub_complete_url(image)
    return url


def get_image_name_and_tag(image_complete_url: URL) -> tuple[str, str]:
    if "sha256" in f"{image_complete_url}":
        parts = image_complete_url.path.split("@")
    else:
        parts = image_complete_url.path.split(":")
    return parts[0].strip("/"), parts[1]


@dataclass
class _PulledStatus:
    size: int
    downloaded: int = 0
    extracted: int = 0


async def _parse_pull_information(
    parsed_progress: _DockerPullImage, *, layer_id_to_size: dict[str, _PulledStatus]
):
    match parsed_progress.status.lower():
        case progress_status if any(
            msg in progress_status
            for msg in [
                "pulling from",
                "pulling fs layer",
                "waiting",
                "digest: ",
            ]
        ):
            # nothing to do here
            pass
        case "downloading":
            assert parsed_progress.id  # nosec
            assert parsed_progress.progress_detail  # nosec
            assert parsed_progress.progress_detail.current  # nosec

            layer_id_to_size.setdefault(
                parsed_progress.id,
                _PulledStatus(parsed_progress.progress_detail.total or 0),
            ).downloaded = parsed_progress.progress_detail.current
        case "verifying checksum" | "download complete":
            assert parsed_progress.id  # nosec
            layer_id_to_size.setdefault(
                parsed_progress.id, _PulledStatus(0)
            ).downloaded = layer_id_to_size.setdefault(
                parsed_progress.id, _PulledStatus(0)
            ).size
        case "extracting":
            assert parsed_progress.id  # nosec
            assert parsed_progress.progress_detail  # nosec
            assert parsed_progress.progress_detail.current  # nosec
            layer_id_to_size.setdefault(
                parsed_progress.id,
                _PulledStatus(parsed_progress.progress_detail.total or 0),
            ).extracted = parsed_progress.progress_detail.current
        case "pull complete":
            assert parsed_progress.id  # nosec
            layer_id_to_size.setdefault(
                parsed_progress.id, _PulledStatus(0)
            ).extracted = layer_id_to_size[parsed_progress.id].size
        case "already exists":
            assert parsed_progress.id  # nosec
            layer_id_to_size.setdefault(
                parsed_progress.id, _PulledStatus(0)
            ).extracted = layer_id_to_size[parsed_progress.id].size
            layer_id_to_size.setdefault(
                parsed_progress.id, _PulledStatus(0)
            ).downloaded = layer_id_to_size[parsed_progress.id].size
        case progress_status if any(
            msg in progress_status
            for msg in [
                "status: downloaded newer image for ",
                "status: image is up to date for ",
            ]
        ):
            for layer_pull_status in layer_id_to_size.values():
                layer_pull_status.downloaded = layer_pull_status.size
                layer_pull_status.extracted = layer_pull_status.size
        case _:
            _logger.warning(
                "unknown pull state: %s. Please check",
                f"{parsed_progress=}",
            )


async def pull_image(
    image: DockerGenericTag,
    registry_settings: RegistrySettings,
    progress_bar: ProgressBarData,
    log_cb: LogCB,
    image_information: DockerImageManifestsV2 | None,
) -> None:
    """pull a docker image to the host machine.


    Arguments:
        image -- the docker image to pull
        registry_settings -- registry settings
        progress_bar -- the current progress bar
        log_cb -- a callback function to send logs to
        image_information -- the image layer information. If this is None, then no fine progress will be retrieved.
    """
    registry_auth = None
    if registry_settings.REGISTRY_URL and registry_settings.REGISTRY_URL in image:
        registry_auth = {
            "username": registry_settings.REGISTRY_USER,
            "password": registry_settings.REGISTRY_PW.get_secret_value(),
        }
    image_short_name = image.split("/")[-1]
    layer_id_to_size: dict[str, _PulledStatus] = {}
    async with AsyncExitStack() as exit_stack:
        # NOTE: docker pulls an image layer by layer
        # NOTE: each layer is first downloaded, then extracted. Extraction usually takes about 2/3 of the time
        # NOTE: so we compute the layer size x3 (1x for downloading, 2x for extracting)
        if image_information:
            layer_id_to_size = {
                layer.digest.removeprefix("sha256:")[:12]: _PulledStatus(layer.size)
                for layer in image_information.layers
            }
        else:
            _logger.warning(
                "pulling image without layer information for %s. Progress will be approximative. TIP: check why this happens",
                f"{image=}",
            )

        client = await exit_stack.enter_async_context(aiodocker.Docker())

        reported_progress = 0.0
        async for pull_progress in client.images.pull(
            image, stream=True, auth=registry_auth
        ):
            try:
                parsed_progress = TypeAdapter(_DockerPullImage).validate_python(
                    pull_progress
                )
            except ValidationError:
                _logger.exception(
                    "Unexpected error while validating '%s'. "
                    "TIP: This is probably an unforeseen pull status text that shall be added to the code. "
                    "The pulling process will still continue.",
                    f"{pull_progress=}",
                )
            else:
                await _parse_pull_information(
                    parsed_progress, layer_id_to_size=layer_id_to_size
                )

            # compute total progress
            total_downloaded_size = sum(
                layer.downloaded for layer in layer_id_to_size.values()
            )
            total_extracted_size = sum(
                layer.extracted for layer in layer_id_to_size.values()
            )
            total_progress = (total_downloaded_size + total_extracted_size) / 2.0
            progress_to_report = total_progress - reported_progress
            await progress_bar.update(progress_to_report)
            reported_progress = total_progress

            await log_cb(
                f"pulling {image_short_name}: {pull_progress}...",
                logging.DEBUG,
            )

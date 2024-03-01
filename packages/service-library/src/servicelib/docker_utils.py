import logging
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Final, Literal

import aiodocker
import aiohttp
import arrow
from models_library.docker import DockerGenericTag
from models_library.generated_models.docker_rest_api import ProgressDetail
from models_library.utils.change_case import snake_to_camel
from pydantic import BaseModel, ByteSize, ValidationError, parse_obj_as
from settings_library.docker_registry import RegistrySettings
from yarl import URL

from .aiohttp import status
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


class DockerImageMultiArchManifestsV2(BaseModel):
    schema_version: Literal[2]
    media_type: Literal["application/vnd.oci.image.index.v1+json"]
    manifests: list[dict[str, Any]]

    class Config:
        frozen = True
        alias_generator = snake_to_camel


_DOCKER_HUB_HOST: Final[str] = "registry-1.docker.io"


def _create_docker_hub_complete_url(image: DockerGenericTag) -> URL:
    if len(image.split("/")) == 1:
        # official image, add library
        return URL(f"https://{_DOCKER_HUB_HOST}/library/{image}")
    return URL(f"https://{_DOCKER_HUB_HOST}/{image}")


def _get_image_complete_url(
    image: DockerGenericTag, registry_settings: RegistrySettings
) -> URL:
    if registry_settings.REGISTRY_URL in image:
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


def _get_image_name_and_tag(image_complete_url: URL) -> tuple[str, str]:
    if "sha256" in f"{image_complete_url}":
        parts = image_complete_url.path.split("@")
    else:
        parts = image_complete_url.path.split(":")
    return parts[0].strip("/"), parts[1]


async def retrieve_image_layer_information(
    image: DockerGenericTag, registry_settings: RegistrySettings
) -> DockerImageManifestsV2:
    async with aiohttp.ClientSession() as session:
        image_complete_url = _get_image_complete_url(image, registry_settings)
        auth = None
        if registry_settings.REGISTRY_URL in f"{image_complete_url}":
            auth = aiohttp.BasicAuth(
                login=registry_settings.REGISTRY_USER,
                password=registry_settings.REGISTRY_PW.get_secret_value(),
            )
        # NOTE: either of type ubuntu:latest or ubuntu@sha256:lksfdjlskfjsldkfj
        docker_image_name, docker_image_tag = _get_image_name_and_tag(
            image_complete_url
        )
        manifest_url = image_complete_url.with_path(
            f"v2/{docker_image_name}/manifests/{docker_image_tag}"
        )

        headers = {
            "Accept": "application/vnd.docker.distribution.manifest.v2+json, application/vnd.oci.image.manifest.v1+json"
        }
        if _DOCKER_HUB_HOST in f"{image_complete_url}":
            # we need the docker hub bearer code (https://stackoverflow.com/questions/57316115/get-manifest-of-a-public-docker-image-hosted-on-docker-hub-using-the-docker-regi)
            bearer_url = URL("https://auth.docker.io/token").with_query(
                {
                    "service": "registry.docker.io",
                    "scope": f"repository:{docker_image_name}:pull",
                }
            )
            async with session.get(bearer_url) as response:
                response.raise_for_status()
                assert response.status == status.HTTP_200_OK  # nosec
                bearer_code = (await response.json())["token"]
                headers |= {
                    "Authorization": f"Bearer {bearer_code}",
                }

        async with session.get(manifest_url, headers=headers, auth=auth) as response:
            # Check if the request was successful
            response.raise_for_status()
            assert response.status == status.HTTP_200_OK  # nosec

            # if the image has multiple architectures
            json_response = await response.json()
        try:
            multi_arch_manifests = parse_obj_as(
                DockerImageMultiArchManifestsV2, json_response
            )
            # find the correct platform
            digest = ""
            for manifest in multi_arch_manifests.manifests:
                if (
                    manifest.get("platform", {}).get("architecture") == "amd64"
                    and manifest.get("platform", {}).get("os") == "linux"
                ):
                    digest = manifest["digest"]
                    break
            manifest_url = image_complete_url.with_path(
                f"v2/{docker_image_name}/manifests/{digest}"
            )
            async with session.get(
                manifest_url, headers=headers, auth=auth
            ) as response:
                response.raise_for_status()
                assert response.status == status.HTTP_200_OK  # nosec
                json_response = await response.json()
                return parse_obj_as(DockerImageManifestsV2, json_response)

        except ValidationError:
            return parse_obj_as(DockerImageManifestsV2, json_response)


class DockerPullImage(BaseModel):
    status: str
    id: str | None
    progress_detail: ProgressDetail | None
    progress: str | None


async def pull_image(
    image: DockerGenericTag,
    registry_settings: RegistrySettings,
    progress_bar: ProgressBarData,
    log_cb: LogCB,
    image_information: DockerImageManifestsV2,
) -> None:
    image_complete_url = _get_image_complete_url(image, registry_settings)
    assert image_complete_url.host  # nosec
    registry_auth = None
    if registry_settings.REGISTRY_URL in f"{image_complete_url}":
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
    async with aiodocker.Docker() as client:
        async with progress_bar.sub_progress(image_layers_total_size) as sub_progress:
            async for pull_progress in client.images.pull(
                image, stream=True, auth=registry_auth
            ):
                parsed_progress = parse_obj_as(DockerPullImage, pull_progress)
                match parsed_progress.status.lower():
                    case "pulling from " | "pulling fs layer" | "waiting":
                        # nothing to do here, this denotes the start of pulling
                        # nothing to do here, this says it pulls some layer with id
                        # nothing to do here, it waits
                        break
                    case "downloading":
                        assert parsed_progress.id  # nosec
                        assert parsed_progress.progress_detail  # nosec
                        assert parsed_progress.progress_detail.current  # nosec
                        layer_id_to_size[
                            parsed_progress.id
                        ].downloaded = parsed_progress.progress_detail.current
                        break
                    case "verifying checksum" | "download complete":
                        assert parsed_progress.id  # nosec
                        layer_id_to_size[
                            parsed_progress.id
                        ].downloaded = layer_id_to_size[parsed_progress.id].size
                        break
                    case "extracting":
                        assert parsed_progress.id  # nosec
                        assert parsed_progress.progress_detail  # nosec
                        assert parsed_progress.progress_detail.current  # nosec
                        layer_id_to_size[
                            parsed_progress.id
                        ].extracted = parsed_progress.progress_detail.current
                        break
                    case "pull complete":
                        assert parsed_progress.id  # nosec
                        layer_id_to_size[
                            parsed_progress.id
                        ].extracted = layer_id_to_size[parsed_progress.id].size
                        break
                    case "digest: " | "status: downloaded newer image for ":
                        break
                    case _:
                        _logger.warning(
                            "unknown pull state: %s. Please check", parsed_progress
                        )
                        break

                # compute total progress
                total_downloaded_size = sum(
                    layer.downloaded for layer in layer_id_to_size.values()
                )
                total_extracted_size = sum(
                    layer.extracted for layer in layer_id_to_size.values()
                )
                sub_progress.set_(total_downloaded_size + total_extracted_size)
                await log_cb(
                    f"pulling {image_complete_url.name}: {pull_progress}...",
                    logging.DEBUG,
                )

import logging
from collections.abc import Awaitable, Callable
from datetime import datetime
from typing import Any, Final, Literal

import aiodocker
import aiohttp
import arrow
from models_library.docker import DockerGenericTag
from models_library.utils.change_case import snake_to_camel
from pydantic import BaseModel, ByteSize, ValidationError, parse_obj_as
from settings_library.docker_registry import RegistrySettings
from yarl import URL

from .aiohttp import status
from .logging_utils import LogLevelInt
from .progress_bar import ProgressBarData


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


async def pull_image(
    image: DockerGenericTag,
    registry_settings: RegistrySettings,
    progress_bar: ProgressBarData,
    log_cb: LogCB,
) -> None:
    image_complete_url = _get_image_complete_url(image, registry_settings)
    assert image_complete_url.host  # nosec
    registry_auth = None
    if registry_settings.REGISTRY_URL in f"{image_complete_url}":
        registry_auth = {
            "username": registry_settings.REGISTRY_USER,
            "password": registry_settings.REGISTRY_PW.get_secret_value(),
        }
    async with aiodocker.Docker() as client:
        async for pull_progress in client.images.pull(
            image, stream=True, auth=registry_auth
        ):
            await log_cb(
                f"pulling {image_complete_url.name}: {pull_progress}...",
                logging.DEBUG,
            )

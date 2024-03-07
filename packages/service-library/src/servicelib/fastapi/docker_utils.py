import logging

import httpx
from models_library.docker import DockerGenericTag
from pydantic import ValidationError, parse_obj_as
from settings_library.docker_registry import RegistrySettings
from yarl import URL

from ..aiohttp import status
from ..docker_utils import (
    DOCKER_HUB_HOST,
    DockerImageManifestsV2,
    DockerImageMultiArchManifestsV2,
    get_image_complete_url,
    get_image_name_and_tag,
)
from ..logging_utils import log_catch

_logger = logging.getLogger(__name__)


async def retrieve_image_layer_information(
    image: DockerGenericTag, registry_settings: RegistrySettings
) -> DockerImageManifestsV2 | None:
    with log_catch(_logger, reraise=False):
        async with httpx.AsyncClient() as client:
            image_complete_url = get_image_complete_url(image, registry_settings)
            auth = None
            if registry_settings.REGISTRY_URL in f"{image_complete_url}":
                auth = httpx.BasicAuth(
                    username=registry_settings.REGISTRY_USER,
                    password=registry_settings.REGISTRY_PW.get_secret_value(),
                )
            # NOTE: either of type ubuntu:latest or ubuntu@sha256:lksfdjlskfjsldkfj
            docker_image_name, docker_image_tag = get_image_name_and_tag(
                image_complete_url
            )
            manifest_url = image_complete_url.with_path(
                f"v2/{docker_image_name}/manifests/{docker_image_tag}"
            )

            headers = {
                "Accept": "application/vnd.docker.distribution.manifest.v2+json, application/vnd.oci.image.manifest.v1+json"
            }
            if DOCKER_HUB_HOST in f"{image_complete_url}":
                # we need the docker hub bearer code (https://stackoverflow.com/questions/57316115/get-manifest-of-a-public-docker-image-hosted-on-docker-hub-using-the-docker-regi)
                bearer_url = URL("https://auth.docker.io/token").with_query(
                    {
                        "service": "registry.docker.io",
                        "scope": f"repository:{docker_image_name}:pull",
                    }
                )
                response = await client.get(f"{bearer_url}")
                response.raise_for_status()
                assert response.status_code == status.HTTP_200_OK  # nosec
                bearer_code = response.json()["token"]
                headers |= {
                    "Authorization": f"Bearer {bearer_code}",
                }

            response = await client.get(f"{manifest_url}", headers=headers, auth=auth)
            # Check if the request was successful
            response.raise_for_status()
            assert response.status_code == status.HTTP_200_OK  # nosec

            # if the image has multiple architectures
            json_response = response.json()
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
                response = await client.get(
                    f"{manifest_url}", headers=headers, auth=auth
                )
                response.raise_for_status()
                assert response.status_code == status.HTTP_200_OK  # nosec
                json_response = response.json()
                return parse_obj_as(DockerImageManifestsV2, json_response)

            except ValidationError:
                return parse_obj_as(DockerImageManifestsV2, json_response)
    return None

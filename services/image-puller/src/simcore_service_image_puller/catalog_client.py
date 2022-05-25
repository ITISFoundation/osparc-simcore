from httpx import AsyncClient, HTTPError, Timeout, codes
from models_library.docker import DockerImage
from pydantic import parse_obj_as

from .errors import ImagePullerError
from .settings import ImagePullerSettings


def get_shared_client(settings: ImagePullerSettings) -> AsyncClient:
    return AsyncClient(
        base_url=settings.IMAGE_PULLER_CATALOG.api_base_url,
        timeout=Timeout(settings.IMAGE_PULLER_CATALOG_REQUEST_TIMEOUT),
    )


async def get_images_to_pull(catalog_client: AsyncClient) -> list[DockerImage]:
    result = await catalog_client.get("/sync/-/images")
    try:
        if result.status_code != codes.OK:
            raise ImagePullerError(
                "Unexpected response from ",
                result.text,
                result.status_code,
                result.headers,
            )
    except HTTPError as err:
        raise ImagePullerError("An error occurred during the request") from err

    return [parse_obj_as(DockerImage, x) for x in result.json()]

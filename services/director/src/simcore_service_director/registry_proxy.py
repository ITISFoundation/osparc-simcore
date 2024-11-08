import enum
import json
import logging
import re
from collections.abc import Mapping
from http import HTTPStatus
from pprint import pformat
from typing import Any, Final, cast

from aiocache import Cache, SimpleMemoryCache  # type: ignore[import-untyped]
from aiohttp import BasicAuth, ClientSession, client_exceptions
from aiohttp.client import ClientTimeout
from fastapi import FastAPI
from servicelib.utils import limited_gather
from tenacity import retry
from tenacity.before_sleep import before_sleep_log
from tenacity.retry import retry_if_result
from tenacity.wait import wait_fixed
from yarl import URL

from .client_session import get_client_session
from .constants import (
    DIRECTOR_SIMCORE_SERVICES_PREFIX,
    ORG_LABELS_TO_SCHEMA_LABELS,
    SERVICE_RUNTIME_SETTINGS,
)
from .core.errors import (
    DirectorRuntimeError,
    RegistryConnectionError,
    ServiceNotAvailableError,
)
from .core.settings import ApplicationSettings, get_application_settings

DEPENDENCIES_LABEL_KEY: str = "simcore.service.dependencies"

NUMBER_OF_RETRIEVED_REPOS: int = 50
NUMBER_OF_RETRIEVED_TAGS: int = 50
_MAX_CONCURRENT_CALLS: Final[int] = 50
VERSION_REG = re.compile(
    r"^(0|[1-9]\d*)(\.(0|[1-9]\d*)){2}(-(0|[1-9]\d*|\d*[-a-zA-Z][-\da-zA-Z]*)(\.(0|[1-9]\d*|\d*[-a-zA-Z][-\da-zA-Z]*))*)?(\+[-\da-zA-Z]+(\.[-\da-zA-Z-]+)*)?$"
)

logger = logging.getLogger(__name__)


class ServiceType(enum.Enum):
    ALL = ""
    COMPUTATIONAL = "comp"
    DYNAMIC = "dynamic"


async def _basic_auth_registry_request(
    app: FastAPI, path: str, method: str, **session_kwargs
) -> tuple[dict, Mapping]:
    app_settings = get_application_settings(app)
    if not app_settings.DIRECTOR_REGISTRY.REGISTRY_URL:
        msg = "URL to registry is not defined"
        raise DirectorRuntimeError(msg=msg)

    url = URL(
        f"{'https' if app_settings.DIRECTOR_REGISTRY.REGISTRY_SSL else 'http'}://{app_settings.DIRECTOR_REGISTRY.REGISTRY_URL}{path}"
    )
    logger.debug("Requesting registry using %s", url)
    # try the registry with basic authentication first, spare 1 call
    resp_data: dict = {}
    resp_headers: Mapping = {}
    auth = (
        BasicAuth(
            login=app_settings.DIRECTOR_REGISTRY.REGISTRY_USER,
            password=app_settings.DIRECTOR_REGISTRY.REGISTRY_PW.get_secret_value(),
        )
        if app_settings.DIRECTOR_REGISTRY.REGISTRY_AUTH
        and app_settings.DIRECTOR_REGISTRY.REGISTRY_USER
        and app_settings.DIRECTOR_REGISTRY.REGISTRY_PW
        else None
    )

    session = get_client_session(app)
    try:
        async with session.request(
            method.lower(), url, auth=auth, **session_kwargs
        ) as response:
            if response.status == HTTPStatus.UNAUTHORIZED:
                logger.debug("Registry unauthorized request: %s", await response.text())
                # basic mode failed, test with other auth mode
                resp_data, resp_headers = await _auth_registry_request(
                    app_settings,
                    url,
                    method,
                    response.headers,
                    session,
                    **session_kwargs,
                )

            elif response.status == HTTPStatus.NOT_FOUND:
                raise ServiceNotAvailableError(service_name=path)

            elif response.status > 399:
                logger.exception(
                    "Unknown error while accessing registry: %s", str(response)
                )
                raise RegistryConnectionError(msg=str(response))

            else:
                # registry that does not need an auth
                resp_data = await response.json(content_type=None)
                resp_headers = response.headers

            return (resp_data, resp_headers)
    except client_exceptions.ClientError as exc:
        logger.exception("Unknown error while accessing registry")
        msg = f"Unknown error while accessing registry: {exc!s}"
        raise DirectorRuntimeError(msg=msg) from exc


async def _auth_registry_request(
    app_settings: ApplicationSettings,
    url: URL,
    method: str,
    auth_headers: Mapping,
    session: ClientSession,
    **kwargs,
) -> tuple[dict, Mapping]:
    if (
        not app_settings.DIRECTOR_REGISTRY.REGISTRY_AUTH
        or not app_settings.DIRECTOR_REGISTRY.REGISTRY_USER
        or not app_settings.DIRECTOR_REGISTRY.REGISTRY_PW
    ):
        msg = "Wrong configuration: Authentication to registry is needed!"
        raise RegistryConnectionError(msg=msg)
    # auth issue let's try some authentication get the auth type
    auth_type = None
    auth_details: dict[str, str] = {}
    for key in auth_headers:
        if str(key).lower() == "www-authenticate":
            auth_type, auth_value = str(auth_headers[key]).split(" ", 1)
            auth_details = {
                x.split("=")[0]: x.split("=")[1].strip('"')
                for x in auth_value.split(",")
            }
            break
    if not auth_type:
        msg = "Unknown registry type: cannot deduce authentication method!"
        raise RegistryConnectionError(msg=msg)
    auth = BasicAuth(
        login=app_settings.DIRECTOR_REGISTRY.REGISTRY_USER,
        password=app_settings.DIRECTOR_REGISTRY.REGISTRY_PW.get_secret_value(),
    )

    # bearer type, it needs a token with all communications
    if auth_type == "Bearer":
        # get the token
        token_url = URL(auth_details["realm"]).with_query(
            service=auth_details["service"], scope=auth_details["scope"]
        )
        async with session.get(token_url, auth=auth, **kwargs) as token_resp:
            if token_resp.status != HTTPStatus.OK:
                msg = f"Unknown error while authentifying with registry: {token_resp!s}"
                raise RegistryConnectionError(msg=msg)
            bearer_code = (await token_resp.json())["token"]
            headers = {"Authorization": f"Bearer {bearer_code}"}
            async with getattr(session, method.lower())(
                url, headers=headers, **kwargs
            ) as resp_wtoken:
                if resp_wtoken.status == HTTPStatus.NOT_FOUND:
                    logger.exception("path to registry not found: %s", url)
                    raise ServiceNotAvailableError(service_name=f"{url}")
                if resp_wtoken.status > 399:
                    logger.exception(
                        "Unknown error while accessing with token authorized registry: %s",
                        str(resp_wtoken),
                    )
                    raise RegistryConnectionError(msg=f"{resp_wtoken}")
                resp_data = await resp_wtoken.json(content_type=None)
                resp_headers = resp_wtoken.headers
                return (resp_data, resp_headers)
    elif auth_type == "Basic":
        # basic authentication should not be since we tried already...
        async with getattr(session, method.lower())(
            url, auth=auth, **kwargs
        ) as resp_wbasic:
            if resp_wbasic.status == HTTPStatus.NOT_FOUND:
                logger.exception("path to registry not found: %s", url)
                raise ServiceNotAvailableError(service_name=f"{url}")
            if resp_wbasic.status > 399:
                logger.exception(
                    "Unknown error while accessing with token authorized registry: %s",
                    str(resp_wbasic),
                )
                raise RegistryConnectionError(msg=f"{resp_wbasic}")
            resp_data = await resp_wbasic.json(content_type=None)
            resp_headers = resp_wbasic.headers
            return (resp_data, resp_headers)
    msg = f"Unknown registry authentification type: {url}"
    raise RegistryConnectionError(msg=msg)


async def registry_request(
    app: FastAPI,
    path: str,
    method: str = "GET",
    no_cache: bool = False,
    **session_kwargs,
) -> tuple[dict, Mapping]:
    logger.debug(
        "Request to registry: path=%s, method=%s. no_cache=%s", path, method, no_cache
    )
    cache: SimpleMemoryCache = app.state.registry_cache_memory
    cache_key = f"{method}_{path}"
    if not no_cache and (cached_response := await cache.get(cache_key)):
        assert isinstance(cached_response, tuple)  # nosec
        return cast(tuple[dict, Mapping], cached_response)

    app_settings = get_application_settings(app)
    response, response_headers = await _basic_auth_registry_request(
        app, path, method, **session_kwargs
    )

    if not no_cache and app_settings.DIRECTOR_REGISTRY_CACHING and method == "GET":
        await cache.set(
            cache_key,
            (response, response_headers),
            ttl=app_settings.DIRECTOR_REGISTRY_CACHING_TTL.total_seconds(),
        )

    return response, response_headers


async def _is_registry_responsive(app: FastAPI) -> bool:
    path = "/v2/"
    try:
        await registry_request(
            app, path, no_cache=True, timeout=ClientTimeout(total=1.0)
        )
        return True
    except (TimeoutError, DirectorRuntimeError) as exc:
        logger.debug("Registry not responsive: %s", exc)
        return False


async def _setup_registry(app: FastAPI) -> None:
    logger.debug("pinging registry...")

    @retry(
        wait=wait_fixed(2),
        before_sleep=before_sleep_log(logger, logging.WARNING),
        retry=retry_if_result(lambda result: result is False),
        reraise=True,
    )
    async def wait_until_registry_responsive(app: FastAPI) -> bool:
        return await _is_registry_responsive(app)

    await wait_until_registry_responsive(app)
    logger.info("Connected to docker registry")


def setup(app: FastAPI) -> None:
    async def on_startup() -> None:
        cache = Cache(Cache.MEMORY)
        assert isinstance(cache, SimpleMemoryCache)  # nosec
        app.state.registry_cache_memory = cache
        await _setup_registry(app)

    async def on_shutdown() -> None:
        # nothing to do here
        ...

    app.add_event_handler("startup", on_startup)
    app.add_event_handler("shutdown", on_shutdown)


async def _list_repositories(app: FastAPI) -> list[str]:
    logger.debug("listing repositories")
    # if there are more repos, the Link will be available in the response headers until none available
    path = f"/v2/_catalog?n={NUMBER_OF_RETRIEVED_REPOS}"
    repos_list: list = []
    while True:
        result, headers = await registry_request(app, path)
        if result["repositories"]:
            repos_list.extend(result["repositories"])
        if "Link" not in headers:
            break
        path = str(headers["Link"]).split(";")[0].strip("<>")
    logger.debug("listed %s repositories", len(repos_list))
    return repos_list


async def list_image_tags(app: FastAPI, image_key: str) -> list[str]:
    logger.debug("listing image tags in %s", image_key)
    image_tags: list = []
    # get list of image tags
    path = f"/v2/{image_key}/tags/list?n={NUMBER_OF_RETRIEVED_TAGS}"
    while True:
        tags, headers = await registry_request(app, path)
        if tags["tags"]:
            image_tags.extend([tag for tag in tags["tags"] if VERSION_REG.match(tag)])
        if "Link" not in headers:
            break
        path = str(headers["Link"]).split(";")[0].strip("<>")
    logger.debug("Found %s image tags in %s", len(image_tags), image_key)
    return image_tags


_DOCKER_CONTENT_DIGEST_HEADER = "Docker-Content-Digest"


async def get_image_digest(app: FastAPI, image: str, tag: str) -> str | None:
    """Returns image manifest digest number or None if fails to obtain it

    The manifest digest is essentially a SHA256 hash of the image manifest

    SEE https://distribution.github.io/distribution/spec/api/#digest-header
    """
    path = f"/v2/{image}/manifests/{tag}"
    _, headers = await registry_request(app, path)

    headers = headers or {}
    return headers.get(_DOCKER_CONTENT_DIGEST_HEADER, None)


async def get_image_labels(
    app: FastAPI, image: str, tag: str
) -> tuple[dict[str, str], str | None]:
    """Returns image labels and the image manifest digest"""

    logger.debug("getting image labels of %s:%s", image, tag)
    path = f"/v2/{image}/manifests/{tag}"
    request_result, headers = await registry_request(app, path)
    v1_compatibility_key = json.loads(request_result["history"][0]["v1Compatibility"])
    container_config: dict[str, Any] = v1_compatibility_key.get(
        "container_config", v1_compatibility_key["config"]
    )
    labels: dict[str, str] = container_config["Labels"]

    headers = headers or {}
    manifest_digest: str | None = headers.get(_DOCKER_CONTENT_DIGEST_HEADER, None)

    logger.debug("retrieved labels of image %s:%s", image, tag)

    return (labels, manifest_digest)


async def get_image_details(
    app: FastAPI, image_key: str, image_tag: str
) -> dict[str, Any]:
    image_details: dict = {}
    labels, image_manifest_digest = await get_image_labels(app, image_key, image_tag)

    if image_manifest_digest:
        # Adds manifest as extra key in the response similar to org.opencontainers.image.base.digest
        # SEE https://github.com/opencontainers/image-spec/blob/main/annotations.md#pre-defined-annotation-keys
        image_details.update({"image_digest": image_manifest_digest})

    if not labels:
        return image_details
    for key in labels:
        if not key.startswith("io.simcore."):
            continue
        try:
            label_data = json.loads(labels[key])
            for label_key in label_data:
                image_details[label_key] = label_data[label_key]
        except json.decoder.JSONDecodeError:
            logging.exception(
                "Error while decoding json formatted data from %s:%s",
                image_key,
                image_tag,
            )
            # silently skip this repo
            return {}

    return image_details


async def get_repo_details(app: FastAPI, image_key: str) -> list[dict[str, Any]]:

    image_tags = await list_image_tags(app, image_key)
    results = await limited_gather(
        *[get_image_details(app, image_key, tag) for tag in image_tags],
        reraise=False,
        _logger=logger,
        limit=_MAX_CONCURRENT_CALLS,
    )
    return [result for result in results if not isinstance(result, BaseException)]


async def list_services(app: FastAPI, service_type: ServiceType) -> list[dict]:
    logger.debug("getting list of services")
    repos = await _list_repositories(app)
    # get the services repos
    prefixes = []
    if service_type in [ServiceType.DYNAMIC, ServiceType.ALL]:
        prefixes.append(_get_prefix(ServiceType.DYNAMIC))
    if service_type in [ServiceType.COMPUTATIONAL, ServiceType.ALL]:
        prefixes.append(_get_prefix(ServiceType.COMPUTATIONAL))
    repos = [x for x in repos if str(x).startswith(tuple(prefixes))]
    logger.debug("retrieved list of repos : %s", repos)

    # only list as service if it actually contains the necessary labels
    results = await limited_gather(
        *[get_repo_details(app, repo) for repo in repos],
        reraise=False,
        _logger=logger,
        limit=_MAX_CONCURRENT_CALLS,
    )

    return [
        service
        for repo_details in results
        if isinstance(repo_details, list)
        for service in repo_details
    ]


async def list_interactive_service_dependencies(
    app: FastAPI, service_key: str, service_tag: str
) -> list[dict]:
    image_labels, _ = await get_image_labels(app, service_key, service_tag)
    dependency_keys = []
    if DEPENDENCIES_LABEL_KEY in image_labels:
        try:
            dependencies = json.loads(image_labels[DEPENDENCIES_LABEL_KEY])
            dependency_keys = [
                {"key": dependency["key"], "tag": dependency["tag"]}
                for dependency in dependencies
            ]

        except json.decoder.JSONDecodeError:
            logging.exception(
                "Incorrect json formatting in %s, skipping...",
                image_labels[DEPENDENCIES_LABEL_KEY],
            )

    return dependency_keys


def _get_prefix(service_type: ServiceType) -> str:
    return f"{DIRECTOR_SIMCORE_SERVICES_PREFIX}/{service_type.value}/"


def get_service_first_name(image_key: str) -> str:
    if str(image_key).startswith(_get_prefix(ServiceType.DYNAMIC)):
        service_name_suffixes = str(image_key)[len(_get_prefix(ServiceType.DYNAMIC)) :]
    elif str(image_key).startswith(_get_prefix(ServiceType.COMPUTATIONAL)):
        service_name_suffixes = str(image_key)[
            len(_get_prefix(ServiceType.COMPUTATIONAL)) :
        ]
    else:
        return "invalid service"

    logger.debug(
        "retrieved service name from repo %s : %s", image_key, service_name_suffixes
    )
    return service_name_suffixes.split("/")[0]


def get_service_last_names(image_key: str) -> str:
    if str(image_key).startswith(_get_prefix(ServiceType.DYNAMIC)):
        service_name_suffixes = str(image_key)[len(_get_prefix(ServiceType.DYNAMIC)) :]
    elif str(image_key).startswith(_get_prefix(ServiceType.COMPUTATIONAL)):
        service_name_suffixes = str(image_key)[
            len(_get_prefix(ServiceType.COMPUTATIONAL)) :
        ]
    else:
        return "invalid service"
    service_last_name = str(service_name_suffixes).replace("/", "_")
    logger.debug(
        "retrieved service last name from repo %s : %s", image_key, service_last_name
    )
    return service_last_name


CONTAINER_SPEC_ENTRY_NAME = "ContainerSpec".lower()
RESOURCES_ENTRY_NAME = "Resources".lower()


def _validate_kind(entry_to_validate: dict[str, Any], kind_name: str):
    for element in (
        entry_to_validate.get("value", {})
        .get("Reservations", {})
        .get("GenericResources", [])
    ):
        if element.get("DiscreteResourceSpec", {}).get("Kind") == kind_name:
            return True
    return False


async def get_service_extras(
    app: FastAPI, image_key: str, image_tag: str
) -> dict[str, Any]:
    # check physical node requirements
    # all nodes require "CPU"
    app_settings = get_application_settings(app)
    result: dict[str, Any] = {
        "node_requirements": {
            "CPU": app_settings.DIRECTOR_DEFAULT_MAX_NANO_CPUS / 1.0e09,
            "RAM": app_settings.DIRECTOR_DEFAULT_MAX_MEMORY,
        }
    }

    labels, _ = await get_image_labels(app, image_key, image_tag)
    logger.debug("Compiling service extras from labels %s", pformat(labels))

    if SERVICE_RUNTIME_SETTINGS in labels:
        service_settings: list[dict[str, Any]] = json.loads(
            labels[SERVICE_RUNTIME_SETTINGS]
        )
        for entry in service_settings:
            entry_name = entry.get("name", "").lower()
            entry_value = entry.get("value")
            invalid_with_msg = None

            if entry_name == RESOURCES_ENTRY_NAME:
                if entry_value and isinstance(entry_value, dict):
                    res_limit = entry_value.get("Limits", {})
                    res_reservation = entry_value.get("Reservations", {})
                    # CPU
                    result["node_requirements"]["CPU"] = (
                        float(res_limit.get("NanoCPUs", 0))
                        or float(res_reservation.get("NanoCPUs", 0))
                        or app_settings.DIRECTOR_DEFAULT_MAX_NANO_CPUS
                    ) / 1.0e09
                    # RAM
                    result["node_requirements"]["RAM"] = (
                        res_limit.get("MemoryBytes", 0)
                        or res_reservation.get("MemoryBytes", 0)
                        or app_settings.DIRECTOR_DEFAULT_MAX_MEMORY
                    )
                else:
                    invalid_with_msg = f"invalid type for resource [{entry_value}]"

                # discrete resources (custom made ones) ---
                # check if the service requires GPU support
                if not invalid_with_msg and _validate_kind(entry, "VRAM"):

                    result["node_requirements"]["GPU"] = 1
                if not invalid_with_msg and _validate_kind(entry, "MPI"):
                    result["node_requirements"]["MPI"] = 1

            elif entry_name == CONTAINER_SPEC_ENTRY_NAME:
                # NOTE: some minor validation
                # expects {'name': 'ContainerSpec', 'type': 'ContainerSpec', 'value': {'Command': [...]}}
                if (
                    entry_value
                    and isinstance(entry_value, dict)
                    and "Command" in entry_value
                ):
                    result["container_spec"] = entry_value
                else:
                    invalid_with_msg = f"invalid container_spec [{entry_value}]"

            if invalid_with_msg:
                logger.warning(
                    "%s entry [%s] encoded in settings labels of service image %s:%s",
                    invalid_with_msg,
                    entry,
                    image_key,
                    image_tag,
                )

    # get org labels
    result.update(
        {
            sl: labels[dl]
            for dl, sl in ORG_LABELS_TO_SCHEMA_LABELS.items()
            if dl in labels
        }
    )

    logger.debug("Following service extras were compiled: %s", pformat(result))

    return result

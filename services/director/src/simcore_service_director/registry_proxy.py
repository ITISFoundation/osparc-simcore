#pylint: disable=C0111
import asyncio
import enum
import json
import logging
from typing import Dict, List, Tuple

from aiohttp import BasicAuth, ClientSession, client_exceptions, web
from simcore_service_director import config, exceptions
from simcore_service_director.cache_request_decorator import cache_requests
from yarl import URL

from .config import APP_CLIENT_SESSION_KEY

DEPENDENCIES_LABEL_KEY: str = 'simcore.service.dependencies'

NUMBER_OF_RETRIEVED_REPOS: int = 50
NUMBER_OF_RETRIEVED_TAGS: int = 50

_logger = logging.getLogger(__name__)

class ServiceType(enum.Enum):
    ALL: str = ""
    COMPUTATIONAL: str = "comp"
    DYNAMIC: str = "dynamic"

async def _auth_registry_request(url: URL, method: str, auth_headers: Dict, session: ClientSession) -> Tuple[Dict, Dict]:
    if not config.REGISTRY_AUTH or not config.REGISTRY_USER or not config.REGISTRY_PW:
        raise exceptions.RegistryConnectionError("Wrong configuration: Authentication to registry is needed!")
    # auth issue let's try some authentication get the auth type
    auth_type = None
    auth_details: Dict[str, str] = {}
    for key in auth_headers:
        if str(key).lower() == "www-authenticate":
            auth_type, auth_value = str(auth_headers[key]).split(" ", 1)
            auth_details = {x.split("=")[0]:x.split("=")[1].strip('"') for x in auth_value.split(",")}
            break
    if not auth_type:
        raise exceptions.RegistryConnectionError("Unknown registry type: cannot deduce authentication method!")
    auth = BasicAuth(login=config.REGISTRY_USER, password=config.REGISTRY_PW)

    # bearer type, it needs a token with all communications
    if auth_type == "Bearer":
        # get the token
        token_url = URL(auth_details["realm"]).with_query(service=auth_details["service"], scope=auth_details["scope"])
        async with session.get(token_url, auth=auth) as token_resp:
            if not token_resp.status == 200:
                raise exceptions.RegistryConnectionError("Unknown error while authentifying with registry: {}".format(str(token_resp)))
            bearer_code = (await token_resp.json())["token"]
            headers = {"Authorization": "Bearer {}".format(bearer_code)}
            async with getattr(session, method.lower())(url, headers=headers) as resp_wtoken:
                if resp_wtoken.status == 404:
                    _logger.exception("path to registry not found: %s", url)
                    raise exceptions.ServiceNotAvailableError(str(url))
                if resp_wtoken.status > 399:
                    _logger.exception("Unknown error while accessing with token authorized registry: %s", str(resp_wtoken))
                    raise exceptions.RegistryConnectionError(str(resp_wtoken))
                resp_data = await resp_wtoken.json(content_type=None)
                resp_headers = resp_wtoken.headers
                return (resp_data, resp_headers)
    elif auth_type == "Basic":
        # basic authentication
        async with getattr(session, method.lower())(url, auth=auth) as resp_wbasic:
            if resp_wbasic.status == 404:
                _logger.exception("path to registry not found: %s", url)
                raise exceptions.ServiceNotAvailableError(str(url))
            if resp_wbasic.status > 399:
                _logger.exception("Unknown error while accessing with token authorized registry: %s", str(resp_wbasic))
                raise exceptions.RegistryConnectionError(str(resp_wbasic))
            resp_data = await resp_wbasic.json(content_type=None)
            resp_headers = resp_wbasic.headers
            return (resp_data, resp_headers)
    raise exceptions.RegistryConnectionError("Unknown registry authentification type: {}".format(url))


@cache_requests
async def _registry_request(app: web.Application, path: URL, method: str ="GET") -> Tuple[Dict, Dict]:
    if not config.REGISTRY_URL:
        raise exceptions.DirectorException("URL to registry is not defined")

    url = URL("{scheme}://{url}".format(scheme="https" if config.REGISTRY_SSL else "http",
                                url=config.REGISTRY_URL))
    url = url.join(path)
    # try the registry with basic authentication first, spare 1 call
    resp_data: Dict = {}
    resp_headers: Dict = {}
    auth = BasicAuth(login=config.REGISTRY_USER, password=config.REGISTRY_PW) \
        if config.REGISTRY_AUTH and config.REGISTRY_USER and config.REGISTRY_PW \
            else None

    session = app[APP_CLIENT_SESSION_KEY]
    try:
        async with getattr(session, method.lower())(url, auth=auth) as response:
            if response.status == 404:
                _logger.exception("path to registry not found: %s", url)
                raise exceptions.ServiceNotAvailableError(str(path))
            if response.status == 401:
                resp_data, resp_headers = await _auth_registry_request(url, method, response.headers, session)
            elif response.status > 399:
                _logger.exception("Unknown error while accessing registry: %s", str(response))
                raise exceptions.RegistryConnectionError(str(response))
            else:
                # registry that does not need an auth
                resp_data = await response.json(content_type=None)
                resp_headers = response.headers

            return (resp_data, resp_headers)
    except client_exceptions.ClientError as exc:
        _logger.exception("Unknown error while accessing registry: %s", str(exc))
        raise exceptions.RegistryConnectionError(f"Unknown error while accessing registry: {str(exc)}")

async def _list_repositories(app: web.Application) -> List[str]:
    _logger.debug("listing repositories")
    # if there are more repos, the Link will be available in the response headers until none available
    path = URL("v2/_catalog?n={}".format(NUMBER_OF_RETRIEVED_REPOS))
    repos_list: List = []
    while True:
        result, headers = await _registry_request(app, path)
        if result["repositories"]:
            repos_list.extend(result["repositories"])
        if "Link" not in headers:
            break
        path = URL(str(headers["Link"]).split(";")[0].strip("<>"))
    _logger.debug("listed %s repositories", len(repos_list))
    return repos_list

async def list_image_tags(app: web.Application, image_key: str) -> List[str]:
    _logger.debug("listing image tags in %s", image_key)
    image_tags: List = []
    # get list of image tags
    path = URL("v2/{}/tags/list?n={}".format(image_key, NUMBER_OF_RETRIEVED_TAGS))
    while True:
        tags, headers = await _registry_request(app, path)
        if tags["tags"]:
            image_tags.extend(tags["tags"])
        if "Link" not in headers:
            break
        path = URL(str(headers["Link"]).split(";")[0].strip("<>"))
    _logger.debug("Found %s image tags in %s", len(image_tags), image_key)
    return image_tags

async def get_image_labels(app: web.Application, image: str, tag: str) -> Dict:
    _logger.debug("getting image labels of %s:%s", image, tag)
    path = URL("v2/{}/manifests/{}".format(image, tag))
    request_result, _ = await _registry_request(app, path)
    labels = json.loads(request_result["history"][0]["v1Compatibility"])["container_config"]["Labels"]
    _logger.debug("retrieved labels of image %s:%s: %s", image, tag, request_result)
    return labels

async def get_image_details(app: web.Application, image_key: str, image_tag: str) -> Dict:
    image_tags: Dict = {}
    labels = await get_image_labels(app, image_key, image_tag)
    if not labels:
        return image_tags
    for key in labels:
        if not key.startswith("io.simcore."):
            continue
        try:
            label_data = json.loads(labels[key])
            for label_key in label_data.keys():
                image_tags[label_key] = label_data[label_key]
        except json.decoder.JSONDecodeError:
            logging.exception("Error while decoding json formatted data from %s:%s", image_key, image_tag)
            # silently skip this repo
            return {}

    return image_tags

async def get_repo_details(app: web.Application, image_key: str) -> List[Dict]:
    repo_details = []
    image_tags = await list_image_tags(app, image_key)
    tasks = [get_image_details(app, image_key, tag) for tag in image_tags]
    results = await asyncio.gather(*tasks)
    for image_details in results:
        if image_details:
            repo_details.append(image_details)
    return repo_details

async def list_services(app: web.Application, service_type: ServiceType) -> List[Dict]:
    _logger.debug("getting list of services")
    repos = await _list_repositories(app)
    # get the services repos
    prefixes = []
    if service_type in [ServiceType.DYNAMIC, ServiceType.ALL]:
        prefixes.append(_get_prefix(ServiceType.DYNAMIC))
    if service_type in [ServiceType.COMPUTATIONAL, ServiceType.ALL]:
        prefixes.append(_get_prefix(ServiceType.COMPUTATIONAL))
    repos = [x for x in repos if str(x).startswith(tuple(prefixes))]
    _logger.debug("retrieved list of repos : %s", repos)

    # only list as service if it actually contains the necessary labels
    tasks = [get_repo_details(app, repo) for repo in repos]
    results = await asyncio.gather(*tasks, return_exceptions=True)
    services = []
    for repo_details in results:
        if repo_details and isinstance(repo_details, list):
            services.extend(repo_details)
        elif isinstance(repo_details, Exception):
            _logger.error("Exception occured while listing services %s", repo_details)
    return services

async def list_interactive_service_dependencies(app: web.Application, service_key: str, service_tag: str) -> List[Dict]:
    image_labels = await get_image_labels(app, service_key, service_tag)
    dependency_keys = []
    if DEPENDENCIES_LABEL_KEY in image_labels:
        try:
            dependencies = json.loads(image_labels[DEPENDENCIES_LABEL_KEY])
            for dependency in dependencies:
                dependency_keys.append({"key":dependency['key'], "tag":dependency['tag']})
        except json.decoder.JSONDecodeError:
            logging.exception("Incorrect json formatting in %s, skipping...", image_labels[DEPENDENCIES_LABEL_KEY])

    return dependency_keys

def _get_prefix(service_type: ServiceType) -> str:
    return "{}/{}/".format(config.SIMCORE_SERVICES_PREFIX, service_type.value)

def get_service_first_name(image_key: str) -> str:
    if str(image_key).startswith(_get_prefix(ServiceType.DYNAMIC)):
        service_name_suffixes = str(image_key)[len(_get_prefix(ServiceType.DYNAMIC)):]
    elif str(image_key).startswith(_get_prefix(ServiceType.COMPUTATIONAL)):
        service_name_suffixes = str(image_key)[len(_get_prefix(ServiceType.COMPUTATIONAL)):]
    else:
        return "invalid service"

    _logger.debug("retrieved service name from repo %s : %s", image_key, service_name_suffixes)
    return service_name_suffixes.split('/')[0]

def get_service_last_names(image_key: str) -> str:
    if str(image_key).startswith(_get_prefix(ServiceType.DYNAMIC)):
        service_name_suffixes = str(image_key)[len(_get_prefix(ServiceType.DYNAMIC)):]
    elif str(image_key).startswith(_get_prefix(ServiceType.COMPUTATIONAL)):
        service_name_suffixes = str(image_key)[len(_get_prefix(ServiceType.COMPUTATIONAL)):]
    else:
        return "invalid service"
    service_last_name = str(service_name_suffixes).replace("/", "_")
    _logger.debug("retrieved service last name from repo %s : %s", image_key, service_last_name)
    return service_last_name

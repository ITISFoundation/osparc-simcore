#pylint: disable=C0111
import enum
import json
import logging
from typing import Dict, List, Tuple

import aiohttp
from yarl import URL

from . import config, exceptions

DEPENDENCIES_LABEL_KEY = 'simcore.service.dependencies'

NUMBER_OF_RETRIEVED_REPOS = 5
NUMBER_OF_RETRIEVED_TAGS = 5

_logger = logging.getLogger(__name__)

class ServiceType(enum.Enum):
    COMPUTATIONAL = "comp"
    DYNAMIC = "dynamic"

async def _auth_registry_request(url: URL, method: str, auth_headers: Dict) -> Tuple[Dict, Dict]:
    if not config.REGISTRY_AUTH or not config.REGISTRY_USER or not config.REGISTRY_PW:
        raise exceptions.RegistryConnectionError("Wrong configuration: Authentication to registry is needed!")
    # auth issue let's try some authentication get the auth type
    auth_type = None
    auth_details = None
    for key in auth_headers:
        if str(key).lower() == "www-authenticate":
            auth_type, auth_details = str(auth_headers[key]).split(" ", 1)
            auth_details = {x.split("=")[0]:x.split("=")[1].strip('"') for x in auth_details.split(",")}
            break
    if not auth_type:
        raise exceptions.RegistryConnectionError("Unknown registry type: cannot deduce authentication method!")
    auth = aiohttp.BasicAuth(login=config.REGISTRY_USER, password=config.REGISTRY_PW)

    # bearer type, it needs a token with all communications
    if auth_type == "Bearer":
        async with aiohttp.ClientSession() as session:
            # get the token
            token_url = URL(auth_details["realm"]).with_query(service=auth_details["service"], scope=auth_details["scope"])
            async with session.get(token_url, auth=auth) as token_resp:
                if not token_resp.status == 200:
                    raise exceptions.RegistryConnectionError("Unknown error while authentifying with registry: {}".format(str(token_resp)))
                bearer_code = (await token_resp.json())["token"]
                headers = {"Authorization": "Bearer {}".format(bearer_code)}
                async with getattr(session, method.lower())(url, headers=headers) as resp_wtoken:
                    if resp_wtoken.status > 399:
                        _logger.exception("Unknown error while accessing with token authorized registry: %s", str(resp_wtoken))
                        raise exceptions.RegistryConnectionError(str(resp_wtoken))
                    resp_data = await resp_wtoken.json(content_type=None)
                    resp_headers = resp_wtoken.headers
                    return (resp_data, resp_headers)
    elif auth_type == "Basic":
        async with aiohttp.ClientSession() as session:
            # basic authentication
            async with getattr(session, method.lower())(url, auth=auth) as resp_wbasic:
                if resp_wbasic.status > 399:
                    _logger.exception("Unknown error while accessing with token authorized registry: %s", str(resp_wbasic))
                    raise exceptions.RegistryConnectionError(str(resp_wbasic))
                resp_data = await resp_wbasic.json(content_type=None)
                resp_headers = resp_wbasic.headers
                return (resp_data, resp_headers)
    raise exceptions.RegistryConnectionError("Unknown registry authentification type: {}".format(url))

async def _registry_request(path: URL, method: str ="GET") -> Tuple[Dict, Dict]:
    if not config.REGISTRY_URL:
        raise exceptions.DirectorException("URL to registry is not defined")
    url = URL("{scheme}://{url}".format(scheme="https" if config.REGISTRY_SSL else "http",
                                url=config.REGISTRY_URL))
    url = url.join(path)

    # try the registry
    resp_data = {}
    resp_headers = {}
    async with aiohttp.ClientSession() as session:
        async with getattr(session, method.lower())(url) as response:
            if response.status == 404:
                _logger.exception("path to registry not found: %s", url)
                raise exceptions.ServiceNotAvailableError(path)
            if response.status == 401:
                resp_data, resp_headers = await _auth_registry_request(url, method, response.headers)
            elif response.status > 399:
                _logger.exception("Unknown error while accessing registry: %s", str(response))
                raise exceptions.RegistryConnectionError(str(response))
            else:
                # registry that does not need an auth
                resp_data = await response.json(content_type=None)
                resp_headers = response.headers

            return (resp_data, resp_headers)

async def _list_repositories() -> List[str]:
    # if there are more repos, the Link will be available in the response headers until none available
    loop = True
    request = URL("v2/_catalog?n={}".format(NUMBER_OF_RETRIEVED_REPOS))
    repos_list = []
    while loop:
        result, headers = await _registry_request(request)
        if result["repositories"]:
            repos_list.extend(result["repositories"])
        request = URL(str(headers["Link"]).split(";")[0].strip("<>")) if "Link" in headers else None
        loop = "Link" in headers
    return repos_list

async def _get_image_details(image_key: str, image_tag: str) -> Dict:
    image_tags = {}
    request = URL("v2/{}/manifests/{}".format(image_key, image_tag))
    label_data, _ = await _registry_request(request)
    labels = json.loads(label_data["history"][0]["v1Compatibility"])["container_config"]["Labels"]
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

async def _list_image_tags(image_key: str) -> List[Dict]:
    image_tags = []
    # get list of repo versions
    loop = True
    request = URL("v2/{}/tags/list?n={}".format(image_key, NUMBER_OF_RETRIEVED_TAGS))
    while loop:
        tags, headers = await _registry_request(request)
        if tags["tags"]:
            image_tags.extend(tags["tags"])
        request = URL(str(headers["Link"]).split(";")[0].strip("<>")) if "Link" in headers else None
        loop = "Link" in headers
    return image_tags

async def _get_repo_details(image_key: str) -> List[Dict]:
    repo_details = []
    image_tags = await _list_image_tags(image_key)
    for tag in image_tags:
        image_details = await _get_image_details(image_key, tag)
        if image_details:
            repo_details.append(image_details)
    return repo_details

async def _list_services(service_type: ServiceType) -> List[List[Dict]]:
    _logger.debug("getting list of services")
    repos = await _list_repositories()
    # get the services repos
    filtered_repos = [repo for repo in repos if str(repo).startswith(_get_prefix(service_type))]
    _logger.debug("retrieved list of repos : %s", filtered_repos)

    # only list as service if it actually contains the necessary labels
    services = []
    for repo in filtered_repos:
        details = await _get_repo_details(repo)
        for repo_detail in details:
            services.append(repo_detail)

    return services

async def list_computational_services() -> List[List[Dict]]:
    return await _list_services(ServiceType.COMPUTATIONAL)

async def list_interactive_services() -> List[List[Dict]]:
    return await _list_services(ServiceType.DYNAMIC)

async def get_service_details(service_key: str, service_version: str) -> List[Dict]:
    return await _get_image_details(service_key, service_version)

async def retrieve_list_of_image_tags(image_key: str):
    return await _list_image_tags(image_key)

async def list_interactive_service_dependencies(service_key: str, service_tag: str) -> List[Dict]:
    image_labels = await retrieve_labels_of_image(service_key, service_tag)
    dependency_keys = []
    if DEPENDENCIES_LABEL_KEY in image_labels:
        try:
            dependencies = json.loads(image_labels[DEPENDENCIES_LABEL_KEY])
            for dependency in dependencies:
                dependency_keys.append({"key":dependency['key'], "tag":dependency['tag']})
        except json.decoder.JSONDecodeError:
            logging.exception("Incorrect json formatting in %s, skipping...", image_labels[DEPENDENCIES_LABEL_KEY])

    return dependency_keys

async def retrieve_labels_of_image(image: str, tag: str) -> Dict:
    request = URL("v2/{}/manifests/{}".format(image, tag))
    request_result, _ = await _registry_request(request)
    labels = json.loads(request_result["history"][0]["v1Compatibility"])["container_config"]["Labels"]
    _logger.debug("retrieved labels of image %s:%s: %s", image, tag, request_result)
    return labels

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

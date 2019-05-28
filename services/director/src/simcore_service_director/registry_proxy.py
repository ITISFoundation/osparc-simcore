#pylint: disable=C0111
import json
import logging
from typing import Dict, List, Tuple

import aiohttp
from yarl import URL

from . import config, exceptions

INTERACTIVE_SERVICES_PREFIX = 'simcore/services/dynamic/'
COMPUTATIONAL_SERVICES_PREFIX = 'simcore/services/comp/'
DEPENDENCIES_LABEL_KEY = 'simcore.service.dependencies'

_logger = logging.getLogger(__name__)


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
                raise exceptions.RegistryConnectionError(path)
            if response.status == 401:
                if not config.REGISTRY_AUTH or not config.REGISTRY_USER or not config.REGISTRY_PW:
                    raise exceptions.RegistryConnectionError("Wrong configuration: Authentication to registry is needed!")
                # auth issue let's try some authentication get the auth type
                auth_type = None
                auth_details = None
                for key in response.headers:
                    if str(key).lower() == "www-authenticate":
                        auth_type, auth_details = str(response.headers[key]).split(" ", 1)
                        auth_details = {x.split("=")[0]:x.split("=")[1].strip('"') for x in auth_details.split(",")}
                        break
                if not auth_type:
                    raise exceptions.RegistryConnectionError("Unknown registry type: cannot deduce authentication method!")
                auth = aiohttp.BasicAuth(login=config.REGISTRY_USER, password=config.REGISTRY_PW)

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
                            if resp_wtoken.status > 399:
                                _logger.exception("Unknown error while accessing with token authorized registry: %s", str(response))
                                raise exceptions.RegistryConnectionError(str(resp_wtoken))
                            resp_data = await resp_wtoken.json(content_type=None)
                            resp_headers = resp_wtoken.headers
                elif auth_type == "Basic":
                    # basic authentication
                    async with getattr(session, method.lower())(url, auth=auth) as resp_wbasic:
                        if resp_wbasic.status > 399:
                            _logger.exception("Unknown error while accessing with token authorized registry: %s", str(response))
                            raise exceptions.RegistryConnectionError(str(resp_wbasic))
                        resp_data = await resp_wbasic.json(content_type=None)
                        resp_headers = resp_wbasic.headers
            elif response.status > 399:
                _logger.exception("Unknown error while accessing registry: %s", str(response))
                raise exceptions.RegistryConnectionError(str(response))
            else:
                # registry that does not need an auth
                resp_data = await response.json(content_type=None)
                resp_headers = response.headers

            return (resp_data, resp_headers)

async def _retrieve_list_of_repositories() -> List[str]:
    result, headers = await _registry_request('v2/_catalog?n=5')
    repos_list = result["repositories"]
    while "Link" in headers:
        link = str(headers["Link"]).split(";")[0].strip("<>")
        result, headers = await _registry_request(link)
        repos_list.extend(result["repositories"])
    _logger.debug("retrieved list of repos: %s", repos_list)
    return repos_list

async def _get_repo_version_details(repo_key: str, repo_tag: str) -> Dict:
    image_tags = {}
    label_data, _ = await _registry_request("v2/" + repo_key + '/manifests/' + repo_tag)
    labels = json.loads(label_data["history"][0]["v1Compatibility"])["container_config"]["Labels"]
    if not labels:
        return image_tags
    for key in labels:
        if key.startswith("io.simcore."):
            try:
                label_data = json.loads(labels[key])
                for label_key in label_data.keys():
                    image_tags[label_key] = label_data[label_key]
            except json.decoder.JSONDecodeError:
                logging.exception("Error while decoding json formatted data from %s:%s", repo_key, repo_tag)
                # silently skip this repo
                return {}

    return image_tags

async def _get_repo_details(repo: str) -> List[Dict]:
    #pylint: disable=too-many-nested-blocks
    current_repo = []
    # get list of repo versions
    im_data = await _registry_request("v2/" + repo + '/tags/list')
    for tag in im_data['tags']:
        image_tags = await _get_repo_version_details(repo, tag)
        if image_tags:
            current_repo.append(image_tags)

    return current_repo

async def _list_services(service_prefix: str) -> List[List[Dict]]:
    _logger.debug("getting list of computational services")
    list_all_repos = await _retrieve_list_of_repositories()
    # get the services repos
    list_of_specific_repos = [repo for repo in list_all_repos if str(repo).startswith(service_prefix)]
    _logger.debug("retrieved list of computational repos : %s", list_of_specific_repos)
    repositories = []
    # or each repo get all tags details
    for repo in list_of_specific_repos:
        details = await _get_repo_details(repo)
        for repo_detail in details:
            repositories.append(repo_detail)

    return repositories


async def list_computational_services() -> List[List[Dict]]:
    return await _list_services(COMPUTATIONAL_SERVICES_PREFIX)

async def list_interactive_services() -> List[List[Dict]]:
    return await _list_services(INTERACTIVE_SERVICES_PREFIX)

async def get_service_details(service_key: str, service_version: str) -> List[Dict]:
    return await _get_repo_version_details(service_key, service_version)

async def retrieve_list_of_images_in_repo(repository_name: str):
    request_result = await _registry_request("v2/" + repository_name + '/tags/list')
    _logger.debug("retrieved list of images in %s: %s",repository_name, request_result)
    return request_result

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
    request_result = await _registry_request("v2/" + image + '/manifests/' + tag)
    labels = json.loads(request_result["history"][0]["v1Compatibility"])[
        "container_config"]["Labels"]
    _logger.debug("retrieved labels of image %s:%s: %s", image, tag, request_result)
    return labels

def get_service_first_name(repository_name: str) -> str:
    if str(repository_name).startswith(INTERACTIVE_SERVICES_PREFIX):
        service_name_suffixes = str(repository_name)[len(INTERACTIVE_SERVICES_PREFIX):]
    elif str(repository_name).startswith(COMPUTATIONAL_SERVICES_PREFIX):
        service_name_suffixes = str(repository_name)[len(COMPUTATIONAL_SERVICES_PREFIX):]
    else:
        return "invalid service"

    _logger.debug("retrieved service name from repo %s : %s", repository_name, service_name_suffixes)
    return service_name_suffixes.split('/')[0]

def get_service_last_names(repository_name: str) -> str:
    if str(repository_name).startswith(INTERACTIVE_SERVICES_PREFIX):
        service_name_suffixes = str(repository_name)[len(INTERACTIVE_SERVICES_PREFIX):]
    elif str(repository_name).startswith(COMPUTATIONAL_SERVICES_PREFIX):
        service_name_suffixes = str(repository_name)[len(COMPUTATIONAL_SERVICES_PREFIX):]
    else:
        return "invalid service"
    service_last_name = str(service_name_suffixes).replace("/", "_")
    _logger.debug("retrieved service last name from repo %s : %s", repository_name, service_last_name)
    return service_last_name

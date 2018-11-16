#pylint: disable=C0111
import json
import logging
from typing import Dict, List
import aiohttp

from . import config, exceptions

INTERACTIVE_SERVICES_PREFIX = 'simcore/services/dynamic/'
COMPUTATIONAL_SERVICES_PREFIX = 'simcore/services/comp/'
DEPENDENCIES_LABEL_KEY = 'simcore.service.dependencies'
_logger = logging.getLogger(__name__)

async def list_computational_services() -> List[List[Dict]]:
    return await __list_services(COMPUTATIONAL_SERVICES_PREFIX)

async def list_interactive_services() -> List[List[Dict]]:
    return await __list_services(INTERACTIVE_SERVICES_PREFIX)

async def get_service_details(service_key: str, service_version: str) -> List[Dict]:
    return await __get_repo_version_details(service_key, service_version)

async def retrieve_list_of_images_in_repo(repository_name: str):
    request_result = await __registry_request(repository_name + '/tags/list')
    _logger.info("retrieved list of images in %s: %s",repository_name, request_result)
    return request_result

async def list_interactive_service_dependencies(service_key: str, service_tag: str) -> List[Dict]:
    image_labels = await retrieve_labels_of_image(service_key, service_tag)
    dependency_keys = []
    if DEPENDENCIES_LABEL_KEY in image_labels:
        dependencies = json.loads(image_labels[DEPENDENCIES_LABEL_KEY])
        for dependency in dependencies:
            dependency_keys.append({"key":dependency['key'], "tag":dependency['tag']})
    return dependency_keys

async def retrieve_labels_of_image(image: str, tag: str) -> Dict:
    request_result = await __registry_request(image + '/manifests/' + tag)
    labels = json.loads(request_result["history"][0]["v1Compatibility"])[
        "container_config"]["Labels"]
    _logger.info("retrieved labels of image %s:%s: %s", image, tag, request_result)
    return labels

def get_service_first_name(repository_name: str) -> str:
    if str(repository_name).startswith(INTERACTIVE_SERVICES_PREFIX):
        service_name_suffixes = str(repository_name)[len(INTERACTIVE_SERVICES_PREFIX):]
    elif str(repository_name).startswith(COMPUTATIONAL_SERVICES_PREFIX):
        service_name_suffixes = str(repository_name)[len(COMPUTATIONAL_SERVICES_PREFIX):]
    else:
        return "invalid service"

    _logger.info("retrieved service name from repo %s : %s", repository_name, service_name_suffixes)
    return service_name_suffixes.split('/')[0]

def get_service_last_names(repository_name: str) -> str:
    if str(repository_name).startswith(INTERACTIVE_SERVICES_PREFIX):
        service_name_suffixes = str(repository_name)[len(INTERACTIVE_SERVICES_PREFIX):]
    elif str(repository_name).startswith(COMPUTATIONAL_SERVICES_PREFIX):
        service_name_suffixes = str(repository_name)[len(COMPUTATIONAL_SERVICES_PREFIX):]
    else:
        return "invalid service"
    service_last_name = str(service_name_suffixes).replace("/", "_")
    _logger.info("retrieved service last name from repo %s : %s", repository_name, service_last_name)
    return service_last_name

async def __registry_request(path: str, method: str ="GET") -> str:
    if not config.REGISTRY_URL:
        raise exceptions.DirectorException("URL to registry is not defined")

    if config.REGISTRY_SSL:
        api_url = 'https://' + config.REGISTRY_URL + '/v2/' + path
    else:
        api_url = 'http://' + config.REGISTRY_URL + '/v2/' + path

    auth = None
    if config.REGISTRY_AUTH:
        _logger.debug("Authentifying registry...")
        if not config.REGISTRY_USER:
            raise exceptions.DirectorException("User to access to registry is not defined")
        if not config.REGISTRY_PW:
            raise exceptions.DirectorException("PW to access to registry is not defined")
        _logger.debug("Session authorization complete")
        auth = aiohttp.BasicAuth(login=config.REGISTRY_USER, password=config.REGISTRY_PW)

    async with aiohttp.ClientSession(auth=auth) as session:
        async with getattr(session, method.lower())(api_url) as response:
            if response.status == 404:
                _logger.exception("path not found")
                raise exceptions.ServiceNotAvailableError(path, None)
            if response.status > 399:
                _logger.exception("Error while connecting to docker registry")
                raise exceptions.DirectorException(await response.text())
            return await response.json(content_type=None)

async def __retrieve_list_of_repositories() -> List[str]:
    result_json = await __registry_request('_catalog')
    result_json = result_json['repositories']
    _logger.info("retrieved list of repos: %s", result_json)
    return result_json

async def __get_repo_version_details(repo_key: str, repo_tag: str) -> Dict:
    image_tags = {}
    label_data = await __registry_request(repo_key + '/manifests/' + repo_tag)
    labels = json.loads(label_data["history"][0]["v1Compatibility"])["container_config"]["Labels"]
    if labels:
        for key in labels.keys():
            if key.startswith("io.simcore."):
                label_data = json.loads(labels[key])
                for label_key in label_data.keys():
                    image_tags[label_key] = label_data[label_key]
    return image_tags

async def __get_repo_details(repo: str) -> List[Dict]:
    #pylint: disable=too-many-nested-blocks
    current_repo = []
    if "/comp/" in repo or "/dynamic/" in repo:
        # get list of repo versions
        im_data = await __registry_request(repo + '/tags/list')
        tags = im_data['tags']
        if tags:
            for tag in tags:
                image_tags = await __get_repo_version_details(repo, tag)
                if image_tags:
                    current_repo.append(image_tags)

    return current_repo

async def __list_services(service_prefix: str) -> List[List[Dict]]:
    _logger.info("getting list of computational services")
    list_all_repos = await __retrieve_list_of_repositories()
    # get the services repos
    list_of_specific_repos = [repo for repo in list_all_repos if str(repo).startswith(service_prefix)]
    _logger.info("retrieved list of computational repos : %s", list_of_specific_repos)
    repositories = []
    # or each repo get all tags details
    for repo in list_of_specific_repos:
        details = await __get_repo_details(repo)
        for repo_detail in details:
            repositories.append(repo_detail)

    return repositories

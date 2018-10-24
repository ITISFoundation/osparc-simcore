"""[summary]

"""
# pylint: disable=C0111
import json
import logging

from requests import HTTPError, RequestException, Session

from . import exceptions, config

INTERACTIVE_SERVICES_PREFIX = 'simcore/services/dynamic/'
COMPUTATIONAL_SERVICES_PREFIX = 'simcore/services/comp/'
DEPENDENCIES_LABEL_KEY = 'simcore.service.dependencies'
_SESSION = Session()
_logger = logging.getLogger(__name__)

def setup_registry_connection():
    _logger.debug("Setup registry connection started...%s", config.REGISTRY_AUTH)

    # get authentication state or set default value
    if config.REGISTRY_AUTH:
        _logger.debug("Authentifying registry...")
        if not config.REGISTRY_USER:
            raise exceptions.DirectorException("User to access to registry is not defined")
        if not config.REGISTRY_PW:
            raise exceptions.DirectorException("PW to access to registry is not defined")
        _SESSION.auth = (config.REGISTRY_USER, config.REGISTRY_PW)
        _logger.debug("Session authorization complete")

def list_computational_services():
    return __list_services(COMPUTATIONAL_SERVICES_PREFIX)

def list_interactive_services():
    return __list_services(INTERACTIVE_SERVICES_PREFIX)

def get_service_details(service_key, service_version):
    return __get_repo_version_details(service_key, service_version)

def retrieve_list_of_images_in_repo(repository_name):
    request_result = __registry_request(repository_name + '/tags/list')
    result_json = request_result.json()
    _logger.info("retrieved list of images in %s: %s",repository_name, result_json)
    return result_json

def list_interactive_service_dependencies(service_key, service_tag):
    image_labels = retrieve_labels_of_image(service_key, service_tag)
    dependency_keys = []
    if DEPENDENCIES_LABEL_KEY in image_labels:
        dependencies = json.loads(image_labels[DEPENDENCIES_LABEL_KEY])
        for dependency in dependencies:
            dependency_keys.append(dependency['key'])
    return dependency_keys

def retrieve_labels_of_image(image, tag):
    request_result = __registry_request(image + '/manifests/' + tag)
    result_json = request_result.json()
    labels = json.loads(result_json["history"][0]["v1Compatibility"])[
        "container_config"]["Labels"]
    _logger.info("retrieved labels of image %s:%s: %s", image, tag, result_json)
    return labels

def get_service_first_name(repository_name):
    if str(repository_name).startswith(INTERACTIVE_SERVICES_PREFIX):
        service_name_suffixes = str(repository_name)[len(INTERACTIVE_SERVICES_PREFIX):]
    elif str(repository_name).startswith(COMPUTATIONAL_SERVICES_PREFIX):
        service_name_suffixes = str(repository_name)[len(COMPUTATIONAL_SERVICES_PREFIX):]
    else:
        return "invalid service"

    _logger.info("retrieved service name from repo %s : %s", repository_name, service_name_suffixes)
    return service_name_suffixes.split('/')[0]

def get_service_last_names(repository_name):
    if str(repository_name).startswith(INTERACTIVE_SERVICES_PREFIX):
        service_name_suffixes = str(repository_name)[len(INTERACTIVE_SERVICES_PREFIX):]
    elif str(repository_name).startswith(COMPUTATIONAL_SERVICES_PREFIX):
        service_name_suffixes = str(repository_name)[len(COMPUTATIONAL_SERVICES_PREFIX):]
    else:
        return "invalid service"
    service_last_name = str(service_name_suffixes).replace("/", "_")
    _logger.info("retrieved service last name from repo %s : %s", repository_name, service_last_name)
    return service_last_name

def __registry_request(path, method="GET"):
    if not config.REGISTRY_URL:
        raise exceptions.DirectorException("URL to registry is not defined")

    if config.REGISTRY_SSL:
        api_url = 'https://' + config.REGISTRY_URL + '/v2/' + path
    else:
        api_url = 'http://' + config.REGISTRY_URL + '/v2/' + path

    try:
        # r = s.get(api_url, verify=False) #getattr(s, method.lower())(api_url)
        request_result = getattr(_SESSION, method.lower())(api_url)
        _logger.info("Request status: %s",request_result.status_code)
        if request_result.status_code > 399:            
            request_result.raise_for_status()

        return request_result
    except HTTPError as err:
        _logger.exception("HTTP error returned while accessing registry")
        if err.response.status_code == 404:
            raise exceptions.ServiceNotAvailableError(path, None) from err
        raise exceptions.RegistryConnectionError("Error while accessing docker registry" ,err) from err
    except RequestException as err:
        _logger.exception("Error while connecting to docker registry")
        raise exceptions.DirectorException(str(err)) from err

def __retrieve_list_of_repositories():
    request_result = __registry_request('_catalog')
    result_json = request_result.json()['repositories']
    _logger.info("retrieved list of repos: %s", result_json)
    return result_json

def __get_repo_version_details(repo_key, repo_tag):
    image_tags = {}
    label_request = __registry_request(repo_key + '/manifests/' + repo_tag)
    label_data = label_request.json()
    labels = json.loads(label_data["history"][0]["v1Compatibility"])["container_config"]["Labels"]
    if labels:
        for key in labels.keys():
            if key.startswith("io.simcore."):
                label_data = json.loads(labels[key])
                for label_key in label_data.keys():
                    image_tags[label_key] = label_data[label_key]
    return image_tags

def __get_repo_details(repo):
    #pylint: disable=too-many-nested-blocks
    current_repo = []
    if "/comp/" in repo or "/dynamic/" in repo:
        # get list of repo versions
        req_images = __registry_request(repo + '/tags/list')
        im_data = req_images.json()
        tags = im_data['tags']
        if tags:
            for tag in tags:
                image_tags = __get_repo_version_details(repo, tag)
                if image_tags:
                    current_repo.append(image_tags)

    return current_repo

def __list_services(service_prefix):
    _logger.info("getting list of computational services")
    list_all_repos = __retrieve_list_of_repositories()
    # get the services repos
    list_of_specific_repos = [repo for repo in list_all_repos if str(repo).startswith(service_prefix)]
    _logger.info("retrieved list of computational repos : %s", list_of_specific_repos)
    repositories = []
    # or each repo get all tags details
    for repo in list_of_specific_repos:
        details = __get_repo_details(repo)
        for repo_detail in details:
            repositories.append(repo_detail)

    return repositories

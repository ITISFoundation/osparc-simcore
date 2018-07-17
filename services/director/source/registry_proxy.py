"""[summary]

"""
# pylint: disable=C0111
import json
import logging
import os

from requests import RequestException, Session

INTERACTIVE_SERVICES_PREFIX = 'simcore/services/dynamic/'
COMPUTATIONAL_SERVICES_PREFIX = 'simcore/services/comp/'
_SESSION = Session()
_LOGGER = logging.getLogger(__name__)

def setup_registry_connection():
    # get authentication state or set default value
    registry_auth = os.environ.get('REGISTRY_AUTH', False)
    if registry_auth in ("True","true"):
        _SESSION.auth = (os.environ['REGISTRY_USER'], os.environ['REGISTRY_PW'])


def registry_request(path, method="GET"):
    # TODO: is is always ssh?
    api_url = 'https://' + os.environ['REGISTRY_URL'] + '/v2/' + path

    try:
        # r = s.get(api_url, verify=False) #getattr(s, method.lower())(api_url)
        request_result = getattr(_SESSION, method.lower())(api_url)
        if request_result.status_code == 401:
            raise Exception(
                'Return Code was 401, Authentication required / not successful!')
        else:
            return request_result
    except RequestException as err:
        raise RequestException("Problem during docker registry connection: {}".format(err))


def retrieve_list_of_repositories():
    request_result = registry_request('_catalog')
    result_json = request_result.json()['repositories']
    _LOGGER.info("retrieved list of repos: %s", result_json)
    return result_json


def retrieve_list_of_images_in_repo(repository_name):
    request_result = registry_request(repository_name + '/tags/list')
    result_json = request_result.json()
    _LOGGER.info("retrieved list of iamges in %s: %s",repository_name, result_json)
    return result_json


def retrieve_labels_of_image(image, tag):
    request_result = registry_request(image + '/manifests/' + tag)
    result_json = request_result.json()
    labels = json.loads(result_json["history"][0]["v1Compatibility"])[
        "container_config"]["Labels"]
    _LOGGER.info("retrieved labels of image %s:%s: %s", image, tag, result_json)
    return labels


def retrieve_list_of_repos_with_interactive_services():
    # pylint: disable=C0103
    list_all_repos = retrieve_list_of_repositories()
    # get the services repos
    list_of_interactive_repos = [repo for repo in list_all_repos if str(repo).startswith(INTERACTIVE_SERVICES_PREFIX)]
    _LOGGER.info("retrieved list of interactive repos : %s", list_of_interactive_repos)

    # some services are made of several repos
    list_of_interactive_services = {}

    for repo in list_of_interactive_repos:
        service_details = {}
        service_name = get_service_name(repo)        
        # is there already a service with the same name?
        if service_name in list_of_interactive_services:
            list_of_interactive_services[service_name]["repos"].append(repo)
            list_of_interactive_services[service_name]["details"].append(_get_repo_details(repo))
        else:
            list_of_interactive_services[service_name] = service_details[service_name]={
                "repos":[repo],
                "details":[
                    _get_repo_details(repo)
                    ]
                }
        
    return list_of_interactive_services


def retrieve_list_of_interactive_services_with_name(service_name):
    # pylint: disable=C0103
    list_interactive_services_repositories = retrieve_list_of_repos_with_interactive_services()
    if service_name in list_interactive_services_repositories:
        _LOGGER.info("retrieved list of interactive repos with name %s : %s", service_name, list_interactive_services_repositories[service_name]["repos"])
        return list_interactive_services_repositories[service_name]["repos"]
    raise Exception('Invalid service name: ' + service_name)


def get_service_name(repository_name):
    service_name_suffixes = str(repository_name)[len(INTERACTIVE_SERVICES_PREFIX):]
    _LOGGER.info("retrieved service name from repo %s : %s", repository_name, service_name_suffixes)
    return service_name_suffixes.split('/')[0]


def get_service_sub_name(repository_name):
    service_name_suffixes = str(repository_name)[
        len(INTERACTIVE_SERVICES_PREFIX):]
    list_of_suffixes = service_name_suffixes.split('/')
    last_suffix_index = len(list_of_suffixes) - 1
    if last_suffix_index < 0:
        raise Exception('Invalid service name: ' + repository_name)
    _LOGGER.info("retrieved service sub name from repo %s : %s", repository_name, list_of_suffixes)
    return list_of_suffixes[last_suffix_index]

def _get_repo_details(repo):
    #pylint: disable=too-many-nested-blocks
    current_repo = []
    if "/comp/" in repo or "/dynamic/" in repo:
        req_images = registry_request(repo + '/tags/list')
        im_data = req_images.json()
        tags = im_data['tags']
        for tag in tags:
            image_tags = {}
            label_request = registry_request(repo + '/manifests/' + tag)
            label_data = label_request.json()
            labels = json.loads(label_data["history"][0]["v1Compatibility"])["container_config"]["Labels"]
            if labels:
                for key in labels.keys():
                    if key.startswith("io.simcore."):
                        label_data = json.loads(labels[key])
                        for label_key in label_data.keys():
                            image_tags[label_key] = label_data[label_key]
            if image_tags:
                current_repo.append(image_tags)

    return current_repo

def list_computational_services():
    _LOGGER.info("getting list of computational services")
    list_all_repos = retrieve_list_of_repositories()
    # get the services repos
    list_of_comp_repos = [repo for repo in list_all_repos if str(repo).startswith(COMPUTATIONAL_SERVICES_PREFIX)]
    _LOGGER.info("retrieved list of computational repos : %s", list_of_comp_repos)
    repositories = {}
    for repo in list_of_comp_repos:
        details = _get_repo_details(repo)
        if details:
            repositories[repo] = details

    result_json = json.dumps(repositories)


    return result_json

import os
import json
from requests import Session, RequestException

INTERACTIVE_SERVICES_PREFIX = 'simcore/services/'
session = Session()

def setup_registry_connection():
    # get authentication state or set default value
    REGISTRY_AUTH = os.environ.get('REGISTRY_AUTH',False)
    if REGISTRY_AUTH == "True" or REGISTRY_AUTH == "true":
        session.auth = (os.environ['REGISTRY_USER'], os.environ['REGISTRY_PW'])

def registry_request(path, method="GET"):
    api_url = 'https://' + os.environ['REGISTRY_URL'] + '/v2/' + path

    try:
        #r = s.get(api_url, verify=False) #getattr(s, method.lower())(api_url)
        request_result = getattr(session, method.lower())(api_url)
        if request_result.status_code == 401:
            raise Exception('Return Code was 401, Authentication required / not successful!')
        else:
            return request_result
    except RequestException as e:
        raise Exception("Problem during docker registry connection")

def retrieve_list_of_repositories():
    request_result = registry_request('_catalog')
    result_json = request_result.json()['repositories']
    return result_json

def retrieve_list_of_images_in_repo(repository_name):
    request_result = registry_request(repository_name + '/tags/list')
    result_json = request_result.json()
    return result_json

def retrieve_labels_of_image(image, tag):
    request_result = registry_request(image + '/manifests/' + tag)
    result_json = request_result.json()
    labels = json.loads(result_json["history"][0]["v1Compatibility"])["container_config"]["Labels"]
    return labels

def retrieve_list_of_repos_with_interactive_services():
    list_all_repos = retrieve_list_of_repositories()
    # get the services repos
    list_of_interactive_repos = [repo for repo in list_all_repos if str(repo).startswith(INTERACTIVE_SERVICES_PREFIX)]
    return list_of_interactive_repos

def retrieve_list_of_interactive_services_with_name(service_name):
    list_interactive_services_repositories = retrieve_list_of_repos_with_interactive_services()
    # find the ones containing the service name
    list_repos_for_service = []
    [list_repos_for_service.append(i) for i in list_interactive_services_repositories if get_service_name(i) == service_name]
    return list_repos_for_service

def get_service_name(repository_name):
    service_name_suffixes = str(repository_name)[len(INTERACTIVE_SERVICES_PREFIX):]
    return service_name_suffixes.split('/')[0]

def get_service_sub_name(repository_name):
    service_name_suffixes = str(repository_name)[len(INTERACTIVE_SERVICES_PREFIX):]
    list_of_suffixes = service_name_suffixes.split('/')
    last_suffix_index = len(list_of_suffixes) - 1
    if last_suffix_index < 0:
        raise Exception('Invalid service name: ' + repository_name)
    return list_of_suffixes[last_suffix_index]

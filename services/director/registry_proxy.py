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
    listOfAllRepos = retrieve_list_of_repositories()
    # get the services repos
    list_of_interactive_repos = [repo for repo in listOfAllRepos if str(repo).startswith(INTERACTIVE_SERVICES_PREFIX)]
    return list_of_interactive_repos

def get_service_name(repository_name):
    service_name_suffixes = str(repository_name)[len(INTERACTIVE_SERVICES_PREFIX):]
    return service_name_suffixes.split('/')[0]

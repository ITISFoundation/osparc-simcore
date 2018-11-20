# simcore_director_sdk.UsersApi

All URIs are relative to *http://localhost:8001/v0*

Method | HTTP request | Description
------------- | ------------- | -------------
[**root_get**](UsersApi.md#root_get) | **GET** / | Service health-check endpoint
[**running_interactive_services_delete**](UsersApi.md#running_interactive_services_delete) | **DELETE** /running_interactive_services/{service_uuid} | Stops and removes an interactive service from the oSparc platform
[**running_interactive_services_get**](UsersApi.md#running_interactive_services_get) | **GET** /running_interactive_services/{service_uuid} | Succesfully returns if a service with the defined uuid is up and running
[**running_interactive_services_post**](UsersApi.md#running_interactive_services_post) | **POST** /running_interactive_services | Starts an interactive service in the oSparc platform and returns its entrypoint
[**services_by_key_version_get**](UsersApi.md#services_by_key_version_get) | **GET** /services/{service_key}/{service_version} | Returns details of the selected service if available in the oSparc platform
[**services_get**](UsersApi.md#services_get) | **GET** /services | Lists available services in the oSparc platform


# **root_get**
> InlineResponse200 root_get()

Service health-check endpoint

Some general information on the API and state of the service behind

### Example
```python
from __future__ import print_function
import time
import simcore_director_sdk
from simcore_director_sdk.rest import ApiException
from pprint import pprint

# create an instance of the API class
api_instance = simcore_director_sdk.UsersApi()

try:
    # Service health-check endpoint
    api_response = api_instance.root_get()
    pprint(api_response)
except ApiException as e:
    print("Exception when calling UsersApi->root_get: %s\n" % e)
```

### Parameters
This endpoint does not need any parameter.

### Return type

[**InlineResponse200**](InlineResponse200.md)

### Authorization

No authorization required

### HTTP request headers

 - **Content-Type**: Not defined
 - **Accept**: application/json

[[Back to top]](#) [[Back to API list]](../README.md#documentation-for-api-endpoints) [[Back to Model list]](../README.md#documentation-for-models) [[Back to README]](../README.md)

# **running_interactive_services_delete**
> InlineResponse204 running_interactive_services_delete(service_uuid)

Stops and removes an interactive service from the oSparc platform

Stops and removes an interactive service from the oSparc platform

### Example
```python
from __future__ import print_function
import time
import simcore_director_sdk
from simcore_director_sdk.rest import ApiException
from pprint import pprint

# create an instance of the API class
api_instance = simcore_director_sdk.UsersApi()
service_uuid = 123e4567-e89b-12d3-a456-426655440000 # str | The uuid of the service

try:
    # Stops and removes an interactive service from the oSparc platform
    api_response = api_instance.running_interactive_services_delete(service_uuid)
    pprint(api_response)
except ApiException as e:
    print("Exception when calling UsersApi->running_interactive_services_delete: %s\n" % e)
```

### Parameters

Name | Type | Description  | Notes
------------- | ------------- | ------------- | -------------
 **service_uuid** | [**str**](.md)| The uuid of the service | 

### Return type

[**InlineResponse204**](InlineResponse204.md)

### Authorization

No authorization required

### HTTP request headers

 - **Content-Type**: Not defined
 - **Accept**: application/json

[[Back to top]](#) [[Back to API list]](../README.md#documentation-for-api-endpoints) [[Back to Model list]](../README.md#documentation-for-models) [[Back to README]](../README.md)

# **running_interactive_services_get**
> InlineResponse204 running_interactive_services_get(service_uuid)

Succesfully returns if a service with the defined uuid is up and running

Succesfully returns if a service with the defined uuid is up and running

### Example
```python
from __future__ import print_function
import time
import simcore_director_sdk
from simcore_director_sdk.rest import ApiException
from pprint import pprint

# create an instance of the API class
api_instance = simcore_director_sdk.UsersApi()
service_uuid = 123e4567-e89b-12d3-a456-426655440000 # str | The uuid of the service

try:
    # Succesfully returns if a service with the defined uuid is up and running
    api_response = api_instance.running_interactive_services_get(service_uuid)
    pprint(api_response)
except ApiException as e:
    print("Exception when calling UsersApi->running_interactive_services_get: %s\n" % e)
```

### Parameters

Name | Type | Description  | Notes
------------- | ------------- | ------------- | -------------
 **service_uuid** | [**str**](.md)| The uuid of the service | 

### Return type

[**InlineResponse204**](InlineResponse204.md)

### Authorization

No authorization required

### HTTP request headers

 - **Content-Type**: Not defined
 - **Accept**: application/json

[[Back to top]](#) [[Back to API list]](../README.md#documentation-for-api-endpoints) [[Back to Model list]](../README.md#documentation-for-models) [[Back to README]](../README.md)

# **running_interactive_services_post**
> InlineResponse201 running_interactive_services_post(user_id, service_key, service_uuid, service_tag=service_tag)

Starts an interactive service in the oSparc platform and returns its entrypoint

Starts an interactive service in the oSparc platform and returns its entrypoint

### Example
```python
from __future__ import print_function
import time
import simcore_director_sdk
from simcore_director_sdk.rest import ApiException
from pprint import pprint

# create an instance of the API class
api_instance = simcore_director_sdk.UsersApi()
user_id = asdfgj233 # str | The ID of the user that starts the service
service_key = simcore/services/dynamic/3d-viewer # str | The key (url) of the service
service_uuid = 123e4567-e89b-12d3-a456-426655440000 # str | The uuid to assign the service with
service_tag = 1.4 # str | The tag/version of the service (optional)

try:
    # Starts an interactive service in the oSparc platform and returns its entrypoint
    api_response = api_instance.running_interactive_services_post(user_id, service_key, service_uuid, service_tag=service_tag)
    pprint(api_response)
except ApiException as e:
    print("Exception when calling UsersApi->running_interactive_services_post: %s\n" % e)
```

### Parameters

Name | Type | Description  | Notes
------------- | ------------- | ------------- | -------------
 **user_id** | **str**| The ID of the user that starts the service | 
 **service_key** | **str**| The key (url) of the service | 
 **service_uuid** | [**str**](.md)| The uuid to assign the service with | 
 **service_tag** | **str**| The tag/version of the service | [optional] 

### Return type

[**InlineResponse201**](InlineResponse201.md)

### Authorization

No authorization required

### HTTP request headers

 - **Content-Type**: Not defined
 - **Accept**: application/json

[[Back to top]](#) [[Back to API list]](../README.md#documentation-for-api-endpoints) [[Back to Model list]](../README.md#documentation-for-models) [[Back to README]](../README.md)

# **services_by_key_version_get**
> InlineResponse2001 services_by_key_version_get(service_key, service_version)

Returns details of the selected service if available in the oSparc platform

Returns details of the selected service if available in the oSparc platform

### Example
```python
from __future__ import print_function
import time
import simcore_director_sdk
from simcore_director_sdk.rest import ApiException
from pprint import pprint

# create an instance of the API class
api_instance = simcore_director_sdk.UsersApi()
service_key = simcore/services/dynamic/3d-viewer # str | The key (url) of the service
service_version = 1.4 # str | The tag/version of the service

try:
    # Returns details of the selected service if available in the oSparc platform
    api_response = api_instance.services_by_key_version_get(service_key, service_version)
    pprint(api_response)
except ApiException as e:
    print("Exception when calling UsersApi->services_by_key_version_get: %s\n" % e)
```

### Parameters

Name | Type | Description  | Notes
------------- | ------------- | ------------- | -------------
 **service_key** | **str**| The key (url) of the service | 
 **service_version** | **str**| The tag/version of the service | 

### Return type

[**InlineResponse2001**](InlineResponse2001.md)

### Authorization

No authorization required

### HTTP request headers

 - **Content-Type**: Not defined
 - **Accept**: application/json

[[Back to top]](#) [[Back to API list]](../README.md#documentation-for-api-endpoints) [[Back to Model list]](../README.md#documentation-for-models) [[Back to README]](../README.md)

# **services_get**
> InlineResponse2001 services_get(service_type=service_type)

Lists available services in the oSparc platform

Lists available services in the oSparc platform

### Example
```python
from __future__ import print_function
import time
import simcore_director_sdk
from simcore_director_sdk.rest import ApiException
from pprint import pprint

# create an instance of the API class
api_instance = simcore_director_sdk.UsersApi()
service_type = computational # str | The service type:   * computational - a computational service   * interactive - an interactive service  (optional)

try:
    # Lists available services in the oSparc platform
    api_response = api_instance.services_get(service_type=service_type)
    pprint(api_response)
except ApiException as e:
    print("Exception when calling UsersApi->services_get: %s\n" % e)
```

### Parameters

Name | Type | Description  | Notes
------------- | ------------- | ------------- | -------------
 **service_type** | **str**| The service type:   * computational - a computational service   * interactive - an interactive service  | [optional] 

### Return type

[**InlineResponse2001**](InlineResponse2001.md)

### Authorization

No authorization required

### HTTP request headers

 - **Content-Type**: Not defined
 - **Accept**: application/json

[[Back to top]](#) [[Back to API list]](../README.md#documentation-for-api-endpoints) [[Back to Model list]](../README.md#documentation-for-models) [[Back to README]](../README.md)


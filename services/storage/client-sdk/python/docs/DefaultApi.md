# simcore_service_storage_sdk.DefaultApi

All URIs are relative to *http://localhost/v0*

Method | HTTP request | Description
------------- | ------------- | -------------
[**check_action_post**](DefaultApi.md#check_action_post) | **POST** /check/{action} | Test checkpoint to ask server to fail or echo back the transmitted data
[**copy_as_soft_link**](DefaultApi.md#copy_as_soft_link) | **POST** /files/{file_id}:soft-copy | Copy as soft link
[**copy_folders_from_project**](DefaultApi.md#copy_folders_from_project) | **POST** /simcore-s3/folders | Deep copies of all data from source to destination project in s3
[**delete_file**](DefaultApi.md#delete_file) | **DELETE** /locations/{location_id}/files/{fileId} | Deletes file
[**delete_folders_of_project**](DefaultApi.md#delete_folders_of_project) | **DELETE** /simcore-s3/folders/{folder_id} | Deletes all objects within a node_id or within a project_id if node_id is omitted
[**download_file**](DefaultApi.md#download_file) | **GET** /locations/{location_id}/files/{fileId} | Gets download link for file at location
[**get_datasets_metadata**](DefaultApi.md#get_datasets_metadata) | **GET** /locations/{location_id}/datasets | Lists all dataset&#39;s metadata
[**get_file_metadata**](DefaultApi.md#get_file_metadata) | **GET** /locations/{location_id}/files/{fileId}/metadata | Get file metadata
[**get_files_metadata**](DefaultApi.md#get_files_metadata) | **GET** /locations/{location_id}/files/metadata | Lists all file&#39;s metadata
[**get_files_metadata_dataset**](DefaultApi.md#get_files_metadata_dataset) | **GET** /locations/{location_id}/datasets/{dataset_id}/metadata | Get dataset metadata
[**get_status**](DefaultApi.md#get_status) | **GET** /status | checks status of self and connected services
[**get_storage_locations**](DefaultApi.md#get_storage_locations) | **GET** /locations | Lists available storage locations
[**health_check**](DefaultApi.md#health_check) | **GET** / | Service health-check endpoint
[**search_files_starting_with**](DefaultApi.md#search_files_starting_with) | **POST** /simcore-s3/files/metadata:search | Returns metadata for all files matching a pattern
[**synchronise_meta_data_table**](DefaultApi.md#synchronise_meta_data_table) | **POST** /locations/{location_id}:sync | Manually triggers the synchronisation of the file meta data table in the database
[**update_file_meta_data**](DefaultApi.md#update_file_meta_data) | **PATCH** /locations/{location_id}/files/{fileId}/metadata | Update file metadata
[**upload_file**](DefaultApi.md#upload_file) | **PUT** /locations/{location_id}/files/{fileId} | Returns upload link or performs copy operation to datcore


# **check_action_post**
> FakeEnveloped check_action_post(action, data=data, fake=fake)

Test checkpoint to ask server to fail or echo back the transmitted data

### Example

```python
from __future__ import print_function
import time
import simcore_service_storage_sdk
from simcore_service_storage_sdk.rest import ApiException
from pprint import pprint
# Defining the host is optional and defaults to http://localhost/v0
# See configuration.py for a list of all supported configuration parameters.
configuration = simcore_service_storage_sdk.Configuration(
    host = "http://localhost/v0"
)


# Enter a context with an instance of the API client
with simcore_service_storage_sdk.ApiClient() as api_client:
    # Create an instance of the API class
    api_instance = simcore_service_storage_sdk.DefaultApi(api_client)
    action = 'echo' # str |  (default to 'echo')
data = 'data_example' # str |  (optional)
fake = simcore_service_storage_sdk.Fake() # Fake |  (optional)

    try:
        # Test checkpoint to ask server to fail or echo back the transmitted data
        api_response = api_instance.check_action_post(action, data=data, fake=fake)
        pprint(api_response)
    except ApiException as e:
        print("Exception when calling DefaultApi->check_action_post: %s\n" % e)
```

### Parameters

Name | Type | Description  | Notes
------------- | ------------- | ------------- | -------------
 **action** | **str**|  | [default to &#39;echo&#39;]
 **data** | **str**|  | [optional] 
 **fake** | [**Fake**](Fake.md)|  | [optional] 

### Return type

[**FakeEnveloped**](FakeEnveloped.md)

### Authorization

No authorization required

### HTTP request headers

 - **Content-Type**: application/json
 - **Accept**: application/json

### HTTP response details
| Status code | Description | Response headers |
|-------------|-------------|------------------|
**200** | Echoes response based on action |  -  |
**0** | Unexpected error |  -  |

[[Back to top]](#) [[Back to API list]](../README.md#documentation-for-api-endpoints) [[Back to Model list]](../README.md#documentation-for-models) [[Back to README]](../README.md)

# **copy_as_soft_link**
> FileMetaDataEnveloped copy_as_soft_link(file_id, user_id, inline_object1=inline_object1)

Copy as soft link

### Example

```python
from __future__ import print_function
import time
import simcore_service_storage_sdk
from simcore_service_storage_sdk.rest import ApiException
from pprint import pprint
# Defining the host is optional and defaults to http://localhost/v0
# See configuration.py for a list of all supported configuration parameters.
configuration = simcore_service_storage_sdk.Configuration(
    host = "http://localhost/v0"
)


# Enter a context with an instance of the API client
with simcore_service_storage_sdk.ApiClient() as api_client:
    # Create an instance of the API class
    api_instance = simcore_service_storage_sdk.DefaultApi(api_client)
    file_id = 'file_id_example' # str | 
user_id = 56 # int | 
inline_object1 = simcore_service_storage_sdk.InlineObject1() # InlineObject1 |  (optional)

    try:
        # Copy as soft link
        api_response = api_instance.copy_as_soft_link(file_id, user_id, inline_object1=inline_object1)
        pprint(api_response)
    except ApiException as e:
        print("Exception when calling DefaultApi->copy_as_soft_link: %s\n" % e)
```

### Parameters

Name | Type | Description  | Notes
------------- | ------------- | ------------- | -------------
 **file_id** | **str**|  | 
 **user_id** | **int**|  | 
 **inline_object1** | [**InlineObject1**](InlineObject1.md)|  | [optional] 

### Return type

[**FileMetaDataEnveloped**](FileMetaDataEnveloped.md)

### Authorization

No authorization required

### HTTP request headers

 - **Content-Type**: application/json
 - **Accept**: application/json

### HTTP response details
| Status code | Description | Response headers |
|-------------|-------------|------------------|
**200** | Returns link metadata |  -  |
**0** | Unexpected error |  -  |

[[Back to top]](#) [[Back to API list]](../README.md#documentation-for-api-endpoints) [[Back to Model list]](../README.md#documentation-for-models) [[Back to README]](../README.md)

# **copy_folders_from_project**
> Project copy_folders_from_project(user_id, inline_object=inline_object)

Deep copies of all data from source to destination project in s3

### Example

```python
from __future__ import print_function
import time
import simcore_service_storage_sdk
from simcore_service_storage_sdk.rest import ApiException
from pprint import pprint
# Defining the host is optional and defaults to http://localhost/v0
# See configuration.py for a list of all supported configuration parameters.
configuration = simcore_service_storage_sdk.Configuration(
    host = "http://localhost/v0"
)


# Enter a context with an instance of the API client
with simcore_service_storage_sdk.ApiClient() as api_client:
    # Create an instance of the API class
    api_instance = simcore_service_storage_sdk.DefaultApi(api_client)
    user_id = 56 # int | 
inline_object = simcore_service_storage_sdk.InlineObject() # InlineObject |  (optional)

    try:
        # Deep copies of all data from source to destination project in s3
        api_response = api_instance.copy_folders_from_project(user_id, inline_object=inline_object)
        pprint(api_response)
    except ApiException as e:
        print("Exception when calling DefaultApi->copy_folders_from_project: %s\n" % e)
```

### Parameters

Name | Type | Description  | Notes
------------- | ------------- | ------------- | -------------
 **user_id** | **int**|  | 
 **inline_object** | [**InlineObject**](InlineObject.md)|  | [optional] 

### Return type

[**Project**](Project.md)

### Authorization

No authorization required

### HTTP request headers

 - **Content-Type**: application/json
 - **Accept**: application/json

### HTTP response details
| Status code | Description | Response headers |
|-------------|-------------|------------------|
**201** | Data from destination project copied and returns project |  -  |
**0** | Unexpected error |  -  |

[[Back to top]](#) [[Back to API list]](../README.md#documentation-for-api-endpoints) [[Back to Model list]](../README.md#documentation-for-models) [[Back to README]](../README.md)

# **delete_file**
> delete_file(file_id, location_id, user_id)

Deletes file

### Example

```python
from __future__ import print_function
import time
import simcore_service_storage_sdk
from simcore_service_storage_sdk.rest import ApiException
from pprint import pprint
# Defining the host is optional and defaults to http://localhost/v0
# See configuration.py for a list of all supported configuration parameters.
configuration = simcore_service_storage_sdk.Configuration(
    host = "http://localhost/v0"
)


# Enter a context with an instance of the API client
with simcore_service_storage_sdk.ApiClient() as api_client:
    # Create an instance of the API class
    api_instance = simcore_service_storage_sdk.DefaultApi(api_client)
    file_id = 'file_id_example' # str | 
location_id = 'location_id_example' # str | 
user_id = 'user_id_example' # str | 

    try:
        # Deletes file
        api_instance.delete_file(file_id, location_id, user_id)
    except ApiException as e:
        print("Exception when calling DefaultApi->delete_file: %s\n" % e)
```

### Parameters

Name | Type | Description  | Notes
------------- | ------------- | ------------- | -------------
 **file_id** | **str**|  | 
 **location_id** | **str**|  | 
 **user_id** | **str**|  | 

### Return type

void (empty response body)

### Authorization

No authorization required

### HTTP request headers

 - **Content-Type**: Not defined
 - **Accept**: application/json

### HTTP response details
| Status code | Description | Response headers |
|-------------|-------------|------------------|
**204** | everything is OK, but there is no content to return |  -  |
**0** | Unexpected error |  -  |

[[Back to top]](#) [[Back to API list]](../README.md#documentation-for-api-endpoints) [[Back to Model list]](../README.md#documentation-for-models) [[Back to README]](../README.md)

# **delete_folders_of_project**
> delete_folders_of_project(folder_id, user_id, node_id=node_id)

Deletes all objects within a node_id or within a project_id if node_id is omitted

### Example

```python
from __future__ import print_function
import time
import simcore_service_storage_sdk
from simcore_service_storage_sdk.rest import ApiException
from pprint import pprint
# Defining the host is optional and defaults to http://localhost/v0
# See configuration.py for a list of all supported configuration parameters.
configuration = simcore_service_storage_sdk.Configuration(
    host = "http://localhost/v0"
)


# Enter a context with an instance of the API client
with simcore_service_storage_sdk.ApiClient() as api_client:
    # Create an instance of the API class
    api_instance = simcore_service_storage_sdk.DefaultApi(api_client)
    folder_id = 'folder_id_example' # str | 
user_id = 'user_id_example' # str | 
node_id = 'node_id_example' # str |  (optional)

    try:
        # Deletes all objects within a node_id or within a project_id if node_id is omitted
        api_instance.delete_folders_of_project(folder_id, user_id, node_id=node_id)
    except ApiException as e:
        print("Exception when calling DefaultApi->delete_folders_of_project: %s\n" % e)
```

### Parameters

Name | Type | Description  | Notes
------------- | ------------- | ------------- | -------------
 **folder_id** | **str**|  | 
 **user_id** | **str**|  | 
 **node_id** | **str**|  | [optional] 

### Return type

void (empty response body)

### Authorization

No authorization required

### HTTP request headers

 - **Content-Type**: Not defined
 - **Accept**: Not defined

### HTTP response details
| Status code | Description | Response headers |
|-------------|-------------|------------------|
**204** | folder has been successfully deleted |  -  |

[[Back to top]](#) [[Back to API list]](../README.md#documentation-for-api-endpoints) [[Back to Model list]](../README.md#documentation-for-models) [[Back to README]](../README.md)

# **download_file**
> PresignedLinkEnveloped download_file(file_id, location_id, user_id)

Gets download link for file at location

### Example

```python
from __future__ import print_function
import time
import simcore_service_storage_sdk
from simcore_service_storage_sdk.rest import ApiException
from pprint import pprint
# Defining the host is optional and defaults to http://localhost/v0
# See configuration.py for a list of all supported configuration parameters.
configuration = simcore_service_storage_sdk.Configuration(
    host = "http://localhost/v0"
)


# Enter a context with an instance of the API client
with simcore_service_storage_sdk.ApiClient() as api_client:
    # Create an instance of the API class
    api_instance = simcore_service_storage_sdk.DefaultApi(api_client)
    file_id = 'file_id_example' # str | 
location_id = 'location_id_example' # str | 
user_id = 'user_id_example' # str | 

    try:
        # Gets download link for file at location
        api_response = api_instance.download_file(file_id, location_id, user_id)
        pprint(api_response)
    except ApiException as e:
        print("Exception when calling DefaultApi->download_file: %s\n" % e)
```

### Parameters

Name | Type | Description  | Notes
------------- | ------------- | ------------- | -------------
 **file_id** | **str**|  | 
 **location_id** | **str**|  | 
 **user_id** | **str**|  | 

### Return type

[**PresignedLinkEnveloped**](PresignedLinkEnveloped.md)

### Authorization

No authorization required

### HTTP request headers

 - **Content-Type**: Not defined
 - **Accept**: application/json

### HTTP response details
| Status code | Description | Response headers |
|-------------|-------------|------------------|
**200** | Returns presigned link |  -  |
**0** | Unexpected error |  -  |

[[Back to top]](#) [[Back to API list]](../README.md#documentation-for-api-endpoints) [[Back to Model list]](../README.md#documentation-for-models) [[Back to README]](../README.md)

# **get_datasets_metadata**
> DatasetMetaDataArrayEnveloped get_datasets_metadata(location_id, user_id)

Lists all dataset's metadata

### Example

```python
from __future__ import print_function
import time
import simcore_service_storage_sdk
from simcore_service_storage_sdk.rest import ApiException
from pprint import pprint
# Defining the host is optional and defaults to http://localhost/v0
# See configuration.py for a list of all supported configuration parameters.
configuration = simcore_service_storage_sdk.Configuration(
    host = "http://localhost/v0"
)


# Enter a context with an instance of the API client
with simcore_service_storage_sdk.ApiClient() as api_client:
    # Create an instance of the API class
    api_instance = simcore_service_storage_sdk.DefaultApi(api_client)
    location_id = 'location_id_example' # str | 
user_id = 'user_id_example' # str | 

    try:
        # Lists all dataset's metadata
        api_response = api_instance.get_datasets_metadata(location_id, user_id)
        pprint(api_response)
    except ApiException as e:
        print("Exception when calling DefaultApi->get_datasets_metadata: %s\n" % e)
```

### Parameters

Name | Type | Description  | Notes
------------- | ------------- | ------------- | -------------
 **location_id** | **str**|  | 
 **user_id** | **str**|  | 

### Return type

[**DatasetMetaDataArrayEnveloped**](DatasetMetaDataArrayEnveloped.md)

### Authorization

No authorization required

### HTTP request headers

 - **Content-Type**: Not defined
 - **Accept**: application/json

### HTTP response details
| Status code | Description | Response headers |
|-------------|-------------|------------------|
**200** | list of dataset meta-datas |  -  |
**0** | Unexpected error |  -  |

[[Back to top]](#) [[Back to API list]](../README.md#documentation-for-api-endpoints) [[Back to Model list]](../README.md#documentation-for-models) [[Back to README]](../README.md)

# **get_file_metadata**
> FileMetaDataEnveloped get_file_metadata(file_id, location_id, user_id)

Get file metadata

### Example

```python
from __future__ import print_function
import time
import simcore_service_storage_sdk
from simcore_service_storage_sdk.rest import ApiException
from pprint import pprint
# Defining the host is optional and defaults to http://localhost/v0
# See configuration.py for a list of all supported configuration parameters.
configuration = simcore_service_storage_sdk.Configuration(
    host = "http://localhost/v0"
)


# Enter a context with an instance of the API client
with simcore_service_storage_sdk.ApiClient() as api_client:
    # Create an instance of the API class
    api_instance = simcore_service_storage_sdk.DefaultApi(api_client)
    file_id = 'file_id_example' # str | 
location_id = 'location_id_example' # str | 
user_id = 'user_id_example' # str | 

    try:
        # Get file metadata
        api_response = api_instance.get_file_metadata(file_id, location_id, user_id)
        pprint(api_response)
    except ApiException as e:
        print("Exception when calling DefaultApi->get_file_metadata: %s\n" % e)
```

### Parameters

Name | Type | Description  | Notes
------------- | ------------- | ------------- | -------------
 **file_id** | **str**|  | 
 **location_id** | **str**|  | 
 **user_id** | **str**|  | 

### Return type

[**FileMetaDataEnveloped**](FileMetaDataEnveloped.md)

### Authorization

No authorization required

### HTTP request headers

 - **Content-Type**: Not defined
 - **Accept**: application/json

### HTTP response details
| Status code | Description | Response headers |
|-------------|-------------|------------------|
**200** | Returns file metadata |  -  |
**0** | Unexpected error |  -  |

[[Back to top]](#) [[Back to API list]](../README.md#documentation-for-api-endpoints) [[Back to Model list]](../README.md#documentation-for-models) [[Back to README]](../README.md)

# **get_files_metadata**
> FileMetaDataArrayEnveloped get_files_metadata(location_id, user_id, uuid_filter=uuid_filter)

Lists all file's metadata

### Example

```python
from __future__ import print_function
import time
import simcore_service_storage_sdk
from simcore_service_storage_sdk.rest import ApiException
from pprint import pprint
# Defining the host is optional and defaults to http://localhost/v0
# See configuration.py for a list of all supported configuration parameters.
configuration = simcore_service_storage_sdk.Configuration(
    host = "http://localhost/v0"
)


# Enter a context with an instance of the API client
with simcore_service_storage_sdk.ApiClient() as api_client:
    # Create an instance of the API class
    api_instance = simcore_service_storage_sdk.DefaultApi(api_client)
    location_id = 'location_id_example' # str | 
user_id = 'user_id_example' # str | 
uuid_filter = 'uuid_filter_example' # str |  (optional)

    try:
        # Lists all file's metadata
        api_response = api_instance.get_files_metadata(location_id, user_id, uuid_filter=uuid_filter)
        pprint(api_response)
    except ApiException as e:
        print("Exception when calling DefaultApi->get_files_metadata: %s\n" % e)
```

### Parameters

Name | Type | Description  | Notes
------------- | ------------- | ------------- | -------------
 **location_id** | **str**|  | 
 **user_id** | **str**|  | 
 **uuid_filter** | **str**|  | [optional] 

### Return type

[**FileMetaDataArrayEnveloped**](FileMetaDataArrayEnveloped.md)

### Authorization

No authorization required

### HTTP request headers

 - **Content-Type**: Not defined
 - **Accept**: application/json

### HTTP response details
| Status code | Description | Response headers |
|-------------|-------------|------------------|
**200** | list of file meta-datas |  -  |
**0** | Unexpected error |  -  |

[[Back to top]](#) [[Back to API list]](../README.md#documentation-for-api-endpoints) [[Back to Model list]](../README.md#documentation-for-models) [[Back to README]](../README.md)

# **get_files_metadata_dataset**
> FileMetaDataArrayEnveloped get_files_metadata_dataset(location_id, dataset_id, user_id)

Get dataset metadata

### Example

```python
from __future__ import print_function
import time
import simcore_service_storage_sdk
from simcore_service_storage_sdk.rest import ApiException
from pprint import pprint
# Defining the host is optional and defaults to http://localhost/v0
# See configuration.py for a list of all supported configuration parameters.
configuration = simcore_service_storage_sdk.Configuration(
    host = "http://localhost/v0"
)


# Enter a context with an instance of the API client
with simcore_service_storage_sdk.ApiClient() as api_client:
    # Create an instance of the API class
    api_instance = simcore_service_storage_sdk.DefaultApi(api_client)
    location_id = 'location_id_example' # str | 
dataset_id = 'dataset_id_example' # str | 
user_id = 'user_id_example' # str | 

    try:
        # Get dataset metadata
        api_response = api_instance.get_files_metadata_dataset(location_id, dataset_id, user_id)
        pprint(api_response)
    except ApiException as e:
        print("Exception when calling DefaultApi->get_files_metadata_dataset: %s\n" % e)
```

### Parameters

Name | Type | Description  | Notes
------------- | ------------- | ------------- | -------------
 **location_id** | **str**|  | 
 **dataset_id** | **str**|  | 
 **user_id** | **str**|  | 

### Return type

[**FileMetaDataArrayEnveloped**](FileMetaDataArrayEnveloped.md)

### Authorization

No authorization required

### HTTP request headers

 - **Content-Type**: Not defined
 - **Accept**: application/json

### HTTP response details
| Status code | Description | Response headers |
|-------------|-------------|------------------|
**200** | list of file meta-datas |  -  |
**0** | Unexpected error |  -  |

[[Back to top]](#) [[Back to API list]](../README.md#documentation-for-api-endpoints) [[Back to Model list]](../README.md#documentation-for-models) [[Back to README]](../README.md)

# **get_status**
> get_status()

checks status of self and connected services

### Example

```python
from __future__ import print_function
import time
import simcore_service_storage_sdk
from simcore_service_storage_sdk.rest import ApiException
from pprint import pprint
# Defining the host is optional and defaults to http://localhost/v0
# See configuration.py for a list of all supported configuration parameters.
configuration = simcore_service_storage_sdk.Configuration(
    host = "http://localhost/v0"
)


# Enter a context with an instance of the API client
with simcore_service_storage_sdk.ApiClient() as api_client:
    # Create an instance of the API class
    api_instance = simcore_service_storage_sdk.DefaultApi(api_client)
    
    try:
        # checks status of self and connected services
        api_instance.get_status()
    except ApiException as e:
        print("Exception when calling DefaultApi->get_status: %s\n" % e)
```

### Parameters
This endpoint does not need any parameter.

### Return type

void (empty response body)

### Authorization

No authorization required

### HTTP request headers

 - **Content-Type**: Not defined
 - **Accept**: Not defined

### HTTP response details
| Status code | Description | Response headers |
|-------------|-------------|------------------|
**200** | returns app status check |  -  |

[[Back to top]](#) [[Back to API list]](../README.md#documentation-for-api-endpoints) [[Back to Model list]](../README.md#documentation-for-models) [[Back to README]](../README.md)

# **get_storage_locations**
> FileLocationArrayEnveloped get_storage_locations(user_id)

Lists available storage locations

### Example

```python
from __future__ import print_function
import time
import simcore_service_storage_sdk
from simcore_service_storage_sdk.rest import ApiException
from pprint import pprint
# Defining the host is optional and defaults to http://localhost/v0
# See configuration.py for a list of all supported configuration parameters.
configuration = simcore_service_storage_sdk.Configuration(
    host = "http://localhost/v0"
)


# Enter a context with an instance of the API client
with simcore_service_storage_sdk.ApiClient() as api_client:
    # Create an instance of the API class
    api_instance = simcore_service_storage_sdk.DefaultApi(api_client)
    user_id = 'user_id_example' # str | 

    try:
        # Lists available storage locations
        api_response = api_instance.get_storage_locations(user_id)
        pprint(api_response)
    except ApiException as e:
        print("Exception when calling DefaultApi->get_storage_locations: %s\n" % e)
```

### Parameters

Name | Type | Description  | Notes
------------- | ------------- | ------------- | -------------
 **user_id** | **str**|  | 

### Return type

[**FileLocationArrayEnveloped**](FileLocationArrayEnveloped.md)

### Authorization

No authorization required

### HTTP request headers

 - **Content-Type**: Not defined
 - **Accept**: application/json

### HTTP response details
| Status code | Description | Response headers |
|-------------|-------------|------------------|
**200** | List of available storage locations |  -  |
**0** | Unexpected error |  -  |

[[Back to top]](#) [[Back to API list]](../README.md#documentation-for-api-endpoints) [[Back to Model list]](../README.md#documentation-for-models) [[Back to README]](../README.md)

# **health_check**
> HealthCheckEnveloped health_check()

Service health-check endpoint

Some general information on the API and state of the service behind

### Example

```python
from __future__ import print_function
import time
import simcore_service_storage_sdk
from simcore_service_storage_sdk.rest import ApiException
from pprint import pprint
# Defining the host is optional and defaults to http://localhost/v0
# See configuration.py for a list of all supported configuration parameters.
configuration = simcore_service_storage_sdk.Configuration(
    host = "http://localhost/v0"
)


# Enter a context with an instance of the API client
with simcore_service_storage_sdk.ApiClient() as api_client:
    # Create an instance of the API class
    api_instance = simcore_service_storage_sdk.DefaultApi(api_client)
    
    try:
        # Service health-check endpoint
        api_response = api_instance.health_check()
        pprint(api_response)
    except ApiException as e:
        print("Exception when calling DefaultApi->health_check: %s\n" % e)
```

### Parameters
This endpoint does not need any parameter.

### Return type

[**HealthCheckEnveloped**](HealthCheckEnveloped.md)

### Authorization

No authorization required

### HTTP request headers

 - **Content-Type**: Not defined
 - **Accept**: application/json

### HTTP response details
| Status code | Description | Response headers |
|-------------|-------------|------------------|
**200** | Service information |  -  |
**0** | Unexpected error |  -  |

[[Back to top]](#) [[Back to API list]](../README.md#documentation-for-api-endpoints) [[Back to Model list]](../README.md#documentation-for-models) [[Back to README]](../README.md)

# **search_files_starting_with**
> FileMetaDataArrayEnveloped search_files_starting_with(user_id, startswith=startswith)

Returns metadata for all files matching a pattern

### Example

```python
from __future__ import print_function
import time
import simcore_service_storage_sdk
from simcore_service_storage_sdk.rest import ApiException
from pprint import pprint
# Defining the host is optional and defaults to http://localhost/v0
# See configuration.py for a list of all supported configuration parameters.
configuration = simcore_service_storage_sdk.Configuration(
    host = "http://localhost/v0"
)


# Enter a context with an instance of the API client
with simcore_service_storage_sdk.ApiClient() as api_client:
    # Create an instance of the API class
    api_instance = simcore_service_storage_sdk.DefaultApi(api_client)
    user_id = 56 # int | 
startswith = '' # str | matches starting string of the file_uuid (optional) (default to '')

    try:
        # Returns metadata for all files matching a pattern
        api_response = api_instance.search_files_starting_with(user_id, startswith=startswith)
        pprint(api_response)
    except ApiException as e:
        print("Exception when calling DefaultApi->search_files_starting_with: %s\n" % e)
```

### Parameters

Name | Type | Description  | Notes
------------- | ------------- | ------------- | -------------
 **user_id** | **int**|  | 
 **startswith** | **str**| matches starting string of the file_uuid | [optional] [default to &#39;&#39;]

### Return type

[**FileMetaDataArrayEnveloped**](FileMetaDataArrayEnveloped.md)

### Authorization

No authorization required

### HTTP request headers

 - **Content-Type**: Not defined
 - **Accept**: application/json

### HTTP response details
| Status code | Description | Response headers |
|-------------|-------------|------------------|
**200** | list of matching files found |  -  |
**0** | Unexpected error |  -  |

[[Back to top]](#) [[Back to API list]](../README.md#documentation-for-api-endpoints) [[Back to Model list]](../README.md#documentation-for-models) [[Back to README]](../README.md)

# **synchronise_meta_data_table**
> TableSynchronisationEnveloped synchronise_meta_data_table(location_id, dry_run=dry_run, fire_and_forget=fire_and_forget)

Manually triggers the synchronisation of the file meta data table in the database

### Example

```python
from __future__ import print_function
import time
import simcore_service_storage_sdk
from simcore_service_storage_sdk.rest import ApiException
from pprint import pprint
# Defining the host is optional and defaults to http://localhost/v0
# See configuration.py for a list of all supported configuration parameters.
configuration = simcore_service_storage_sdk.Configuration(
    host = "http://localhost/v0"
)


# Enter a context with an instance of the API client
with simcore_service_storage_sdk.ApiClient() as api_client:
    # Create an instance of the API class
    api_instance = simcore_service_storage_sdk.DefaultApi(api_client)
    location_id = 'location_id_example' # str | 
dry_run = True # bool |  (optional) (default to True)
fire_and_forget = False # bool |  (optional) (default to False)

    try:
        # Manually triggers the synchronisation of the file meta data table in the database
        api_response = api_instance.synchronise_meta_data_table(location_id, dry_run=dry_run, fire_and_forget=fire_and_forget)
        pprint(api_response)
    except ApiException as e:
        print("Exception when calling DefaultApi->synchronise_meta_data_table: %s\n" % e)
```

### Parameters

Name | Type | Description  | Notes
------------- | ------------- | ------------- | -------------
 **location_id** | **str**|  | 
 **dry_run** | **bool**|  | [optional] [default to True]
 **fire_and_forget** | **bool**|  | [optional] [default to False]

### Return type

[**TableSynchronisationEnveloped**](TableSynchronisationEnveloped.md)

### Authorization

No authorization required

### HTTP request headers

 - **Content-Type**: Not defined
 - **Accept**: application/json

### HTTP response details
| Status code | Description | Response headers |
|-------------|-------------|------------------|
**200** | An object containing added, changed and removed paths |  -  |
**0** | Unexpected error |  -  |

[[Back to top]](#) [[Back to API list]](../README.md#documentation-for-api-endpoints) [[Back to Model list]](../README.md#documentation-for-models) [[Back to README]](../README.md)

# **update_file_meta_data**
> FileMetaDataEnveloped update_file_meta_data(file_id, location_id, file_meta_data=file_meta_data)

Update file metadata

### Example

```python
from __future__ import print_function
import time
import simcore_service_storage_sdk
from simcore_service_storage_sdk.rest import ApiException
from pprint import pprint
# Defining the host is optional and defaults to http://localhost/v0
# See configuration.py for a list of all supported configuration parameters.
configuration = simcore_service_storage_sdk.Configuration(
    host = "http://localhost/v0"
)


# Enter a context with an instance of the API client
with simcore_service_storage_sdk.ApiClient() as api_client:
    # Create an instance of the API class
    api_instance = simcore_service_storage_sdk.DefaultApi(api_client)
    file_id = 'file_id_example' # str | 
location_id = 'location_id_example' # str | 
file_meta_data = simcore_service_storage_sdk.FileMetaData() # FileMetaData |  (optional)

    try:
        # Update file metadata
        api_response = api_instance.update_file_meta_data(file_id, location_id, file_meta_data=file_meta_data)
        pprint(api_response)
    except ApiException as e:
        print("Exception when calling DefaultApi->update_file_meta_data: %s\n" % e)
```

### Parameters

Name | Type | Description  | Notes
------------- | ------------- | ------------- | -------------
 **file_id** | **str**|  | 
 **location_id** | **str**|  | 
 **file_meta_data** | [**FileMetaData**](FileMetaData.md)|  | [optional] 

### Return type

[**FileMetaDataEnveloped**](FileMetaDataEnveloped.md)

### Authorization

No authorization required

### HTTP request headers

 - **Content-Type**: application/json
 - **Accept**: application/json

### HTTP response details
| Status code | Description | Response headers |
|-------------|-------------|------------------|
**200** | Returns file metadata |  -  |
**0** | Unexpected error |  -  |

[[Back to top]](#) [[Back to API list]](../README.md#documentation-for-api-endpoints) [[Back to Model list]](../README.md#documentation-for-models) [[Back to README]](../README.md)

# **upload_file**
> PresignedLinkEnveloped upload_file(file_id, location_id, user_id, extra_location=extra_location, extra_source=extra_source)

Returns upload link or performs copy operation to datcore

### Example

```python
from __future__ import print_function
import time
import simcore_service_storage_sdk
from simcore_service_storage_sdk.rest import ApiException
from pprint import pprint
# Defining the host is optional and defaults to http://localhost/v0
# See configuration.py for a list of all supported configuration parameters.
configuration = simcore_service_storage_sdk.Configuration(
    host = "http://localhost/v0"
)


# Enter a context with an instance of the API client
with simcore_service_storage_sdk.ApiClient() as api_client:
    # Create an instance of the API class
    api_instance = simcore_service_storage_sdk.DefaultApi(api_client)
    file_id = 'file_id_example' # str | 
location_id = 'location_id_example' # str | 
user_id = 'user_id_example' # str | 
extra_location = 'extra_location_example' # str |  (optional)
extra_source = 'extra_source_example' # str |  (optional)

    try:
        # Returns upload link or performs copy operation to datcore
        api_response = api_instance.upload_file(file_id, location_id, user_id, extra_location=extra_location, extra_source=extra_source)
        pprint(api_response)
    except ApiException as e:
        print("Exception when calling DefaultApi->upload_file: %s\n" % e)
```

### Parameters

Name | Type | Description  | Notes
------------- | ------------- | ------------- | -------------
 **file_id** | **str**|  | 
 **location_id** | **str**|  | 
 **user_id** | **str**|  | 
 **extra_location** | **str**|  | [optional] 
 **extra_source** | **str**|  | [optional] 

### Return type

[**PresignedLinkEnveloped**](PresignedLinkEnveloped.md)

### Authorization

No authorization required

### HTTP request headers

 - **Content-Type**: Not defined
 - **Accept**: application/json

### HTTP response details
| Status code | Description | Response headers |
|-------------|-------------|------------------|
**200** | Returns presigned link |  -  |
**0** | Unexpected error |  -  |

[[Back to top]](#) [[Back to API list]](../README.md#documentation-for-api-endpoints) [[Back to Model list]](../README.md#documentation-for-models) [[Back to README]](../README.md)


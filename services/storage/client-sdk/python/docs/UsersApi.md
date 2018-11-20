# simcore_service_storage_sdk.UsersApi

All URIs are relative to *http://localhost:11111/v0*

Method | HTTP request | Description
------------- | ------------- | -------------
[**check_action_post**](UsersApi.md#check_action_post) | **POST** /check/{action} | Test checkpoint to ask server to fail or echo back the transmitted data
[**delete_file**](UsersApi.md#delete_file) | **DELETE** /locations/{location_id}/files/{fileId} | Deletes File
[**download_file**](UsersApi.md#download_file) | **GET** /locations/{location_id}/files/{fileId} | Returns download link for requested file
[**get_file_metadata**](UsersApi.md#get_file_metadata) | **GET** /locations/{location_id}/files/{fileId}/metadata | Get File Metadata
[**get_files_metadata**](UsersApi.md#get_files_metadata) | **GET** /locations/{location_id}/files/metadata | Get Files Metadata
[**get_storage_locations**](UsersApi.md#get_storage_locations) | **GET** /locations | Get available storage locations
[**health_check**](UsersApi.md#health_check) | **GET** / | Service health-check endpoint
[**update_file_meta_data**](UsersApi.md#update_file_meta_data) | **PATCH** /locations/{location_id}/files/{fileId}/metadata | Update File Metadata
[**upload_file**](UsersApi.md#upload_file) | **PUT** /locations/{location_id}/files/{fileId} | Returns upload link or performs copy operation to datcore


# **check_action_post**
> FakeEnveloped check_action_post(action, data=data, fake_type=fake_type)

Test checkpoint to ask server to fail or echo back the transmitted data

### Example
```python
from __future__ import print_function
import time
import simcore_service_storage_sdk
from simcore_service_storage_sdk.rest import ApiException
from pprint import pprint

# create an instance of the API class
api_instance = simcore_service_storage_sdk.UsersApi()
action = 'echo' # str |  (default to 'echo')
data = 'data_example' # str |  (optional)
fake_type = simcore_service_storage_sdk.FakeType() # FakeType |  (optional)

try:
    # Test checkpoint to ask server to fail or echo back the transmitted data
    api_response = api_instance.check_action_post(action, data=data, fake_type=fake_type)
    pprint(api_response)
except ApiException as e:
    print("Exception when calling UsersApi->check_action_post: %s\n" % e)
```

### Parameters

Name | Type | Description  | Notes
------------- | ------------- | ------------- | -------------
 **action** | **str**|  | [default to &#39;echo&#39;]
 **data** | **str**|  | [optional] 
 **fake_type** | [**FakeType**](FakeType.md)|  | [optional] 

### Return type

[**FakeEnveloped**](FakeEnveloped.md)

### Authorization

No authorization required

### HTTP request headers

 - **Content-Type**: application/json
 - **Accept**: application/json

[[Back to top]](#) [[Back to API list]](../README.md#documentation-for-api-endpoints) [[Back to Model list]](../README.md#documentation-for-models) [[Back to README]](../README.md)

# **delete_file**
> delete_file(file_id, location_id, user_id)

Deletes File

### Example
```python
from __future__ import print_function
import time
import simcore_service_storage_sdk
from simcore_service_storage_sdk.rest import ApiException
from pprint import pprint

# create an instance of the API class
api_instance = simcore_service_storage_sdk.UsersApi()
file_id = 'file_id_example' # str | 
location_id = 'location_id_example' # str | 
user_id = 'user_id_example' # str | 

try:
    # Deletes File
    api_instance.delete_file(file_id, location_id, user_id)
except ApiException as e:
    print("Exception when calling UsersApi->delete_file: %s\n" % e)
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

[[Back to top]](#) [[Back to API list]](../README.md#documentation-for-api-endpoints) [[Back to Model list]](../README.md#documentation-for-models) [[Back to README]](../README.md)

# **download_file**
> PresignedLinkEnveloped download_file(file_id, location_id, user_id)

Returns download link for requested file

### Example
```python
from __future__ import print_function
import time
import simcore_service_storage_sdk
from simcore_service_storage_sdk.rest import ApiException
from pprint import pprint

# create an instance of the API class
api_instance = simcore_service_storage_sdk.UsersApi()
file_id = 'file_id_example' # str | 
location_id = 'location_id_example' # str | 
user_id = 'user_id_example' # str | 

try:
    # Returns download link for requested file
    api_response = api_instance.download_file(file_id, location_id, user_id)
    pprint(api_response)
except ApiException as e:
    print("Exception when calling UsersApi->download_file: %s\n" % e)
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

[[Back to top]](#) [[Back to API list]](../README.md#documentation-for-api-endpoints) [[Back to Model list]](../README.md#documentation-for-models) [[Back to README]](../README.md)

# **get_file_metadata**
> FileMetaDataEnveloped get_file_metadata(file_id, location_id, user_id)

Get File Metadata

### Example
```python
from __future__ import print_function
import time
import simcore_service_storage_sdk
from simcore_service_storage_sdk.rest import ApiException
from pprint import pprint

# create an instance of the API class
api_instance = simcore_service_storage_sdk.UsersApi()
file_id = 'file_id_example' # str | 
location_id = 'location_id_example' # str | 
user_id = 'user_id_example' # str | 

try:
    # Get File Metadata
    api_response = api_instance.get_file_metadata(file_id, location_id, user_id)
    pprint(api_response)
except ApiException as e:
    print("Exception when calling UsersApi->get_file_metadata: %s\n" % e)
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

[[Back to top]](#) [[Back to API list]](../README.md#documentation-for-api-endpoints) [[Back to Model list]](../README.md#documentation-for-models) [[Back to README]](../README.md)

# **get_files_metadata**
> FileMetaDataArrayEnveloped get_files_metadata(location_id, user_id, uuid_filter=uuid_filter)

Get Files Metadata

### Example
```python
from __future__ import print_function
import time
import simcore_service_storage_sdk
from simcore_service_storage_sdk.rest import ApiException
from pprint import pprint

# create an instance of the API class
api_instance = simcore_service_storage_sdk.UsersApi()
location_id = 'location_id_example' # str | 
user_id = 'user_id_example' # str | 
uuid_filter = 'uuid_filter_example' # str |  (optional)

try:
    # Get Files Metadata
    api_response = api_instance.get_files_metadata(location_id, user_id, uuid_filter=uuid_filter)
    pprint(api_response)
except ApiException as e:
    print("Exception when calling UsersApi->get_files_metadata: %s\n" % e)
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

[[Back to top]](#) [[Back to API list]](../README.md#documentation-for-api-endpoints) [[Back to Model list]](../README.md#documentation-for-models) [[Back to README]](../README.md)

# **get_storage_locations**
> FileLocationArrayEnveloped get_storage_locations(user_id)

Get available storage locations

### Example
```python
from __future__ import print_function
import time
import simcore_service_storage_sdk
from simcore_service_storage_sdk.rest import ApiException
from pprint import pprint

# create an instance of the API class
api_instance = simcore_service_storage_sdk.UsersApi()
user_id = 'user_id_example' # str | 

try:
    # Get available storage locations
    api_response = api_instance.get_storage_locations(user_id)
    pprint(api_response)
except ApiException as e:
    print("Exception when calling UsersApi->get_storage_locations: %s\n" % e)
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

# create an instance of the API class
api_instance = simcore_service_storage_sdk.UsersApi()

try:
    # Service health-check endpoint
    api_response = api_instance.health_check()
    pprint(api_response)
except ApiException as e:
    print("Exception when calling UsersApi->health_check: %s\n" % e)
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

[[Back to top]](#) [[Back to API list]](../README.md#documentation-for-api-endpoints) [[Back to Model list]](../README.md#documentation-for-models) [[Back to README]](../README.md)

# **update_file_meta_data**
> FileMetaDataEnveloped update_file_meta_data(file_id, location_id, file_meta_data_type=file_meta_data_type)

Update File Metadata

### Example
```python
from __future__ import print_function
import time
import simcore_service_storage_sdk
from simcore_service_storage_sdk.rest import ApiException
from pprint import pprint

# create an instance of the API class
api_instance = simcore_service_storage_sdk.UsersApi()
file_id = 'file_id_example' # str | 
location_id = 'location_id_example' # str | 
file_meta_data_type = simcore_service_storage_sdk.FileMetaDataType() # FileMetaDataType |  (optional)

try:
    # Update File Metadata
    api_response = api_instance.update_file_meta_data(file_id, location_id, file_meta_data_type=file_meta_data_type)
    pprint(api_response)
except ApiException as e:
    print("Exception when calling UsersApi->update_file_meta_data: %s\n" % e)
```

### Parameters

Name | Type | Description  | Notes
------------- | ------------- | ------------- | -------------
 **file_id** | **str**|  | 
 **location_id** | **str**|  | 
 **file_meta_data_type** | [**FileMetaDataType**](FileMetaDataType.md)|  | [optional] 

### Return type

[**FileMetaDataEnveloped**](FileMetaDataEnveloped.md)

### Authorization

No authorization required

### HTTP request headers

 - **Content-Type**: application/json
 - **Accept**: application/json

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

# create an instance of the API class
api_instance = simcore_service_storage_sdk.UsersApi()
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
    print("Exception when calling UsersApi->upload_file: %s\n" % e)
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

[[Back to top]](#) [[Back to API list]](../README.md#documentation-for-api-endpoints) [[Back to Model list]](../README.md#documentation-for-models) [[Back to README]](../README.md)


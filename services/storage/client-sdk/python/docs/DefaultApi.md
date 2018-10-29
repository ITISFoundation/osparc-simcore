# simcore_storage_sdk.DefaultApi

All URIs are relative to *http://{host}:{port}/v0*

Method | HTTP request | Description
------------- | ------------- | -------------
[**delete_file**](DefaultApi.md#delete_file) | **DELETE** /locations/{location_id}/files/{fileId} | Deletes File
[**download_file**](DefaultApi.md#download_file) | **GET** /locations/{location_id}/files/{fileId} | Returns download link for requested file
[**get_file_metadata**](DefaultApi.md#get_file_metadata) | **GET** /locations/{location_id}/files/{fileId}/metadata | Get File Metadata
[**get_files_metadata**](DefaultApi.md#get_files_metadata) | **GET** /locations/{location_id}/files/metadata | Get Files Metadata
[**get_storage_locations**](DefaultApi.md#get_storage_locations) | **GET** /locations | Get available storage locations
[**update_file_meta_data**](DefaultApi.md#update_file_meta_data) | **PATCH** /locations/{location_id}/files/{fileId}/metadata | Update File Metadata
[**upload_file**](DefaultApi.md#upload_file) | **PUT** /locations/{location_id}/files/{fileId} | Returns upload link or performs copy operation to datcore


# **delete_file**
> delete_file(file_id, location_id, user_id)

Deletes File

### Example
```python
from __future__ import print_function
import time
import simcore_storage_sdk
from simcore_storage_sdk.rest import ApiException
from pprint import pprint

# create an instance of the API class
api_instance = simcore_storage_sdk.DefaultApi()
file_id = 'file_id_example' # str | 
location_id = 'location_id_example' # str | 
user_id = 'user_id_example' # str | 

try:
    # Deletes File
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
 - **Accept**: Not defined

[[Back to top]](#) [[Back to API list]](../README.md#documentation-for-api-endpoints) [[Back to Model list]](../README.md#documentation-for-models) [[Back to README]](../README.md)

# **download_file**
> InlineResponse2004 download_file(file_id, location_id, user_id)

Returns download link for requested file

### Example
```python
from __future__ import print_function
import time
import simcore_storage_sdk
from simcore_storage_sdk.rest import ApiException
from pprint import pprint

# create an instance of the API class
api_instance = simcore_storage_sdk.DefaultApi()
file_id = 'file_id_example' # str | 
location_id = 'location_id_example' # str | 
user_id = 'user_id_example' # str | 

try:
    # Returns download link for requested file
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

[**InlineResponse2004**](InlineResponse2004.md)

### Authorization

No authorization required

### HTTP request headers

 - **Content-Type**: Not defined
 - **Accept**: application/json

[[Back to top]](#) [[Back to API list]](../README.md#documentation-for-api-endpoints) [[Back to Model list]](../README.md#documentation-for-models) [[Back to README]](../README.md)

# **get_file_metadata**
> InlineResponse2003 get_file_metadata(file_id, location_id, user_id)

Get File Metadata

### Example
```python
from __future__ import print_function
import time
import simcore_storage_sdk
from simcore_storage_sdk.rest import ApiException
from pprint import pprint

# create an instance of the API class
api_instance = simcore_storage_sdk.DefaultApi()
file_id = 'file_id_example' # str | 
location_id = 'location_id_example' # str | 
user_id = 'user_id_example' # str | 

try:
    # Get File Metadata
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

[**InlineResponse2003**](InlineResponse2003.md)

### Authorization

No authorization required

### HTTP request headers

 - **Content-Type**: Not defined
 - **Accept**: application/json

[[Back to top]](#) [[Back to API list]](../README.md#documentation-for-api-endpoints) [[Back to Model list]](../README.md#documentation-for-models) [[Back to README]](../README.md)

# **get_files_metadata**
> list[InlineResponse2003] get_files_metadata(location_id, user_id)

Get Files Metadata

### Example
```python
from __future__ import print_function
import time
import simcore_storage_sdk
from simcore_storage_sdk.rest import ApiException
from pprint import pprint

# create an instance of the API class
api_instance = simcore_storage_sdk.DefaultApi()
location_id = 'location_id_example' # str | 
user_id = 'user_id_example' # str | 

try:
    # Get Files Metadata
    api_response = api_instance.get_files_metadata(location_id, user_id)
    pprint(api_response)
except ApiException as e:
    print("Exception when calling DefaultApi->get_files_metadata: %s\n" % e)
```

### Parameters

Name | Type | Description  | Notes
------------- | ------------- | ------------- | -------------
 **location_id** | **str**|  | 
 **user_id** | **str**|  | 

### Return type

[**list[InlineResponse2003]**](InlineResponse2003.md)

### Authorization

No authorization required

### HTTP request headers

 - **Content-Type**: Not defined
 - **Accept**: application/json

[[Back to top]](#) [[Back to API list]](../README.md#documentation-for-api-endpoints) [[Back to Model list]](../README.md#documentation-for-models) [[Back to README]](../README.md)

# **get_storage_locations**
> list[InlineResponse2002] get_storage_locations()

Get available storage locations

### Example
```python
from __future__ import print_function
import time
import simcore_storage_sdk
from simcore_storage_sdk.rest import ApiException
from pprint import pprint

# create an instance of the API class
api_instance = simcore_storage_sdk.DefaultApi()

try:
    # Get available storage locations
    api_response = api_instance.get_storage_locations()
    pprint(api_response)
except ApiException as e:
    print("Exception when calling DefaultApi->get_storage_locations: %s\n" % e)
```

### Parameters
This endpoint does not need any parameter.

### Return type

[**list[InlineResponse2002]**](InlineResponse2002.md)

### Authorization

No authorization required

### HTTP request headers

 - **Content-Type**: Not defined
 - **Accept**: application/json

[[Back to top]](#) [[Back to API list]](../README.md#documentation-for-api-endpoints) [[Back to Model list]](../README.md#documentation-for-models) [[Back to README]](../README.md)

# **update_file_meta_data**
> InlineResponse2003 update_file_meta_data(file_id, location_id, body1=body1)

Update File Metadata

### Example
```python
from __future__ import print_function
import time
import simcore_storage_sdk
from simcore_storage_sdk.rest import ApiException
from pprint import pprint

# create an instance of the API class
api_instance = simcore_storage_sdk.DefaultApi()
file_id = 'file_id_example' # str | 
location_id = 'location_id_example' # str | 
body1 = simcore_storage_sdk.Body1() # Body1 |  (optional)

try:
    # Update File Metadata
    api_response = api_instance.update_file_meta_data(file_id, location_id, body1=body1)
    pprint(api_response)
except ApiException as e:
    print("Exception when calling DefaultApi->update_file_meta_data: %s\n" % e)
```

### Parameters

Name | Type | Description  | Notes
------------- | ------------- | ------------- | -------------
 **file_id** | **str**|  | 
 **location_id** | **str**|  | 
 **body1** | [**Body1**](Body1.md)|  | [optional] 

### Return type

[**InlineResponse2003**](InlineResponse2003.md)

### Authorization

No authorization required

### HTTP request headers

 - **Content-Type**: application/json
 - **Accept**: application/json

[[Back to top]](#) [[Back to API list]](../README.md#documentation-for-api-endpoints) [[Back to Model list]](../README.md#documentation-for-models) [[Back to README]](../README.md)

# **upload_file**
> InlineResponse2004 upload_file(file_id, location_id, user_id, extra_source=extra_source)

Returns upload link or performs copy operation to datcore

### Example
```python
from __future__ import print_function
import time
import simcore_storage_sdk
from simcore_storage_sdk.rest import ApiException
from pprint import pprint

# create an instance of the API class
api_instance = simcore_storage_sdk.DefaultApi()
file_id = 'file_id_example' # str | 
location_id = 'location_id_example' # str | 
user_id = 'user_id_example' # str | 
extra_source = 'extra_source_example' # str |  (optional)

try:
    # Returns upload link or performs copy operation to datcore
    api_response = api_instance.upload_file(file_id, location_id, user_id, extra_source=extra_source)
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
 **extra_source** | **str**|  | [optional] 

### Return type

[**InlineResponse2004**](InlineResponse2004.md)

### Authorization

No authorization required

### HTTP request headers

 - **Content-Type**: Not defined
 - **Accept**: application/json

[[Back to top]](#) [[Back to API list]](../README.md#documentation-for-api-endpoints) [[Back to Model list]](../README.md#documentation-for-models) [[Back to README]](../README.md)


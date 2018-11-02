# simcore_storage_sdk.TestsApi

All URIs are relative to *http://localhost:11111/v0*

Method | HTTP request | Description
------------- | ------------- | -------------
[**check_action_post**](TestsApi.md#check_action_post) | **POST** /check/{action} | Test checkpoint to ask server to fail or echo back the transmitted data


# **check_action_post**
> InlineResponse2001 check_action_post(action, data=data, inline_object=inline_object)

Test checkpoint to ask server to fail or echo back the transmitted data

### Example
```python
from __future__ import print_function
import time
import simcore_storage_sdk
from simcore_storage_sdk.rest import ApiException
from pprint import pprint

# create an instance of the API class
api_instance = simcore_storage_sdk.TestsApi()
action = 'echo' # str |  (default to 'echo')
data = 'data_example' # str |  (optional)
inline_object = simcore_storage_sdk.InlineObject() # InlineObject |  (optional)

try:
    # Test checkpoint to ask server to fail or echo back the transmitted data
    api_response = api_instance.check_action_post(action, data=data, inline_object=inline_object)
    pprint(api_response)
except ApiException as e:
    print("Exception when calling TestsApi->check_action_post: %s\n" % e)
```

### Parameters

Name | Type | Description  | Notes
------------- | ------------- | ------------- | -------------
 **action** | **str**|  | [default to &#39;echo&#39;]
 **data** | **str**|  | [optional] 
 **inline_object** | [**InlineObject**](InlineObject.md)|  | [optional] 

### Return type

[**InlineResponse2001**](InlineResponse2001.md)

### Authorization

No authorization required

### HTTP request headers

 - **Content-Type**: application/json
 - **Accept**: application/json

[[Back to top]](#) [[Back to API list]](../README.md#documentation-for-api-endpoints) [[Back to Model list]](../README.md#documentation-for-models) [[Back to README]](../README.md)


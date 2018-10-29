# simcore_storage_sdk.UsersApi

All URIs are relative to *http://{host}:{port}/v0*

Method | HTTP request | Description
------------- | ------------- | -------------
[**health_check**](UsersApi.md#health_check) | **GET** / | Service health-check endpoint


# **health_check**
> InlineResponse200 health_check()

Service health-check endpoint

Some general information on the API and state of the service behind

### Example
```python
from __future__ import print_function
import time
import simcore_storage_sdk
from simcore_storage_sdk.rest import ApiException
from pprint import pprint

# create an instance of the API class
api_instance = simcore_storage_sdk.UsersApi()

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

[**InlineResponse200**](InlineResponse200.md)

### Authorization

No authorization required

### HTTP request headers

 - **Content-Type**: Not defined
 - **Accept**: application/json

[[Back to top]](#) [[Back to API list]](../README.md#documentation-for-api-endpoints) [[Back to Model list]](../README.md#documentation-for-models) [[Back to README]](../README.md)


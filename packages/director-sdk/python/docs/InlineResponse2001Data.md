# InlineResponse2001Data

## Properties
Name | Type | Description | Notes
------------ | ------------- | ------------- | -------------
**entry_point** | **str** | The entry point where the service provides its interface if specified | [optional] 
**published_port** | **int** | The ports where the service provides its interface | 
**service_basepath** | **str** | different base path where current service is mounted otherwise defaults to root | [optional] [default to '']
**service_host** | **str** | service host name within the network | 
**service_key** | **str** | distinctive name for the node based on the docker registry path | 
**service_message** | **str** | the service message | [optional] 
**service_port** | **int** | port to access the service within the network | 
**service_state** | **str** | the service state * &#39;pending&#39; - The service is waiting for resources to start * &#39;pulling&#39; - The service is being pulled from the registry * &#39;starting&#39; - The service is starting * &#39;running&#39; - The service is running * &#39;complete&#39; - The service completed * &#39;failed&#39; - The service failed to start  | 
**service_uuid** | **str** | The UUID attached to this service | 
**service_version** | **str** | semantic version number | 

[[Back to Model list]](../README.md#documentation-for-models) [[Back to API list]](../README.md#documentation-for-api-endpoints) [[Back to README]](../README.md)



# Project

## Properties
Name | Type | Description | Notes
------------ | ------------- | ------------- | -------------
**uuid** | **str** | project unique identifier |
**name** | **str** | project name |
**description** | **str** | longer one-line description about the project |
**prj_owner** | **str** | user email |
**access_rights** | **dict(str, object)** | object containing the GroupID as key and read/write/execution permissions as value |
**creation_date** | **str** | project creation date |
**last_change_date** | **str** | last save date |
**thumbnail** | **str** | url of the latest screenshot of the project |
**workbench** | **dict(str, object)** |  |
**ui** | [**ProjectUi**](ProjectUi.md) |  | [optional]
**tags** | **list[int]** |  | [optional]
**classifiers** | **list[str]** | Contains the reference to the project classifiers | [optional]
**dev** | **object** | object used for development purposes only | [optional]
**state** | **object** | Project state | [optional]
**quality** | **object** | Object containing Quality Assessment related data | [optional]

[[Back to Model list]](../README.md#documentation-for-models) [[Back to API list]](../README.md#documentation-for-api-endpoints) [[Back to README]](../README.md)

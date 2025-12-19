# pylint:disable=unused-variable
# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name
# pylint:disable=protected-access


import warnings
from copy import deepcopy
from typing import Any

import aiobotocore.client

# Original botocore _make_api_call function
orig = aiobotocore.client.AioBaseClient._make_api_call  # noqa: SLF001


def _patch_send_command(self, operation_name, api_params) -> Any:
    # NOTE: send_command is not completely patched by moto, therefore we need this specific mock
    # https://docs.getmoto.org/en/latest/docs/services/patching_other_services.html
    # this might change with new versions of moto
    warnings.warn(
        "moto is missing SendCommand mock with InstanceIds as Targets, therefore it is manually mocked."
        " TIP: periodically check if it gets updated https://docs.getmoto.org/en/latest/docs/services/ssm.html#ssm",
        UserWarning,
        stacklevel=1,
    )

    assert "Targets" in api_params, "Targets is missing in the API call"
    assert len(api_params["Targets"]) == 1, (
        "Targets for patched SendCommand should have only one item"
    )
    target_data = api_params["Targets"][0]
    assert "Key" in target_data
    assert "Values" in target_data
    target_key = target_data["Key"]
    assert target_key == "InstanceIds", (
        "Targets for patched SendCommand should have InstanceIds as key"
    )
    instance_ids = target_data["Values"]
    new_api_params = deepcopy(api_params)
    new_api_params.pop("Targets")
    new_api_params["InstanceIds"] = instance_ids
    return orig(self, operation_name, new_api_params)


def _patch_describe_instance_information(
    self, operation_name, api_params
) -> dict[str, Any]:
    warnings.warn(
        "moto is missing the describe_instance_information function, therefore it is manually mocked."
        "TIP: periodically check if it gets updated https://docs.getmoto.org/en/latest/docs/services/ssm.html#ssm",
        UserWarning,
        stacklevel=1,
    )
    return {"InstanceInformationList": [{"PingStatus": "Online"}]}


def _patch_cancel_command(self, operation_name, api_params) -> dict[str, Any]:
    warnings.warn(
        "moto is missing the cancel_command function, therefore it is manually mocked."
        "TIP: periodically check if it gets updated https://docs.getmoto.org/en/latest/docs/services/ssm.html#ssm",
        UserWarning,
        stacklevel=1,
    )
    return {}


# Mocked aiobotocore _make_api_call function
async def patched_aiobotocore_make_api_call(self, operation_name, api_params):
    # For example for the Access Analyzer service
    # As you can see the operation_name has the list_analyzers snake_case form but
    # we are using the ListAnalyzers form.
    # Rationale -> https://github.com/boto/botocore/blob/develop/botocore/client.py#L810:L816
    if operation_name == "SendCommand":
        return await _patch_send_command(self, operation_name, api_params)
    if operation_name == "CancelCommand":
        return _patch_cancel_command(self, operation_name, api_params)
    if operation_name == "DescribeInstanceInformation":
        return _patch_describe_instance_information(self, operation_name, api_params)

    # If we don't want to patch the API call
    return await orig(self, operation_name, api_params)

import aiobotocore.client

# NOTE: send_command is not completely patched by moto, therefore we need this specific mock
# https://docs.getmoto.org/en/latest/docs/services/patching_other_services.html
# this might change with new versions of moto
# Original botocore _make_api_call function
orig = aiobotocore.client.AioBaseClient._make_api_call


# Mocked botocore _make_api_call function
def mock_make_api_call(self, operation_name, kwarg):
    # For example for the Access Analyzer service
    # As you can see the operation_name has the list_analyzers snake_case form but
    # we are using the ListAnalyzers form.
    # Rationale -> https://github.com/boto/botocore/blob/develop/botocore/client.py#L810:L816
    print("I AM HERE")
    print(operation_name)
    if operation_name == "ListAnalyzers":
        return {
            "analyzers": [
                {
                    "arn": "ARN",
                    "name": "Test Analyzer",
                    "status": "Enabled",
                    "findings": 0,
                    "tags": "",
                    "type": "ACCOUNT",
                    "region": "eu-west-1",
                }
            ]
        }
    # If we don't want to patch the API call
    return orig(self, operation_name, kwarg)

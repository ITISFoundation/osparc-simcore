# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable
# pylint: disable=too-many-arguments


import yaml
from simcore_service_director import resources


def test_server_specs():
    with resources.stream(resources.RESOURCE_OPEN_API) as fh:
        specs = yaml.safe_load(fh)

        # client-sdk current limitation
        #  - hooks to first server listed in oas
        default_server = specs["servers"][0]
        assert (
            default_server["url"] == "http://{host}:{port}/{version}"
        ), "Invalid convention"

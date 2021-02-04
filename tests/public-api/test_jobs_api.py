# pylint:disable=unused-variable
# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name

import osparc
import pytest


@pytest.fixture()
def jobs_api(api_client):
    return osparc.JobsApi(api_client)


# TODO: placeholder for future tests on jobs APIs

# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=W0212

import openapi_core
import pytest

from servicelib import openapi


@pytest.fixture
def multi_doc_oas(here):
    openapi_path = here / "data" / "oas3-parts" / "petstore.yaml"
    assert openapi_path.exists()
    return openapi_path

@pytest.fixture
def single_doc_oas(here):
    openapi_path = here / "data" / "oas3" / "petstore.yaml"
    assert openapi_path.exists()
    return openapi_path

async def test_multi_doc_openapi_specs(multi_doc_oas, single_doc_oas):
    try:
        # specs created out of multiple documents
        multi_doc_specs = await openapi.create_openapi_specs(multi_doc_oas)

        # a single-document spec
        single_doc_specs = await openapi.create_openapi_specs(single_doc_oas)

    except Exception: # pylint: disable=W0703
        pytest.fail("Failed specs validation")


    assert single_doc_specs.paths.keys() == multi_doc_specs.paths.keys()

    assert single_doc_specs.paths['/tags'].operations['get'].operation_id == \
           multi_doc_specs.paths['/tags'].operations['get'].operation_id




# TODO: move this test to api/specs

@pytest.fixture
def webserver_oas(osparc_simcore_root_dir):
    openapi_path = osparc_simcore_root_dir / "api/specs/webserver/v0/openapi.yaml"
    assert openapi_path.exists()
    return openapi_path


def test_can_create_specs(webserver_oas):
    spec_dict, spec_url = openapi._load_from_path(webserver_oas)
    specs = openapi_core.create_spec(spec_dict, spec_url)
    assert specs

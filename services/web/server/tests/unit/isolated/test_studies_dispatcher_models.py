# pylint: disable=protected-access
# pylint: disable=redefined-outer-name
# pylint: disable=too-many-arguments
# pylint: disable=unused-argument
# pylint: disable=unused-variable


from typing import Any
from urllib.parse import parse_qs

import pytest
from aiohttp.test_utils import make_mocked_request
from models_library.utils.pydantic_tools_extension import parse_obj_or_none
from pydantic import ByteSize, TypeAdapter
from servicelib.aiohttp.requests_validation import parse_request_query_parameters_as
from simcore_service_webserver.studies_dispatcher._models import (
    FileParams,
    ServiceParams,
)
from simcore_service_webserver.studies_dispatcher._redirects_handlers import (
    FileQueryParams,
    ServiceAndFileParams,
)
from yarl import URL

_SIZEBYTES = TypeAdapter(ByteSize).validate_python("3MiB")

# SEE https://github.com/ITISFoundation/osparc-simcore/issues/3951#issuecomment-1489992645
# AWS download links have query arg
_DOWNLOAD_LINK = "https://discover-use1.s3.amazonaws.com/23/2/files/dataset_description.xlsx?AWSAccessKeyId=AKIAQNJEWKCFAOLGQTY6&Signature=K229A0CE5Z5OU2PRi2cfrfgLLEw%3D&x-amz-request-payer=requester&Expires=1605545606"
_DOWNLOAD_LINK1 = "https://prod-discover-publish-use1.s3.amazonaws.com/44/2/files/code/model_validation.ipynb?response-content-type=application%2Foctet-stream&AWSAccessKeyId=AKIAVPHN3KJHIM77P4OY&Signature=WPBOqEyTnUIKfxRFaC2YnyO85XI%3D&x-amz-request-payer=requester&Expires=1680171597"
_DOWNLOAD_LINK2 = "https://raw.githubusercontent.com/pcrespov/osparc-sample-studies/master/files%20samples/sample.ipynb"
_DOWNLOAD_LINK3 = (
    "https://raw.githubusercontent.com/rawgraphs/raw/master/data/orchestra.csv"
)


@pytest.mark.parametrize(
    "url_in,expected_download_link",
    [
        (
            f'{URL("http://localhost:9081").with_path("/view").with_query(file_type="CSV", viewer_key="simcore/services/comp/foo", viewer_version="1.0.0", file_size="300", file_name="orchestra.csv", download_link=_DOWNLOAD_LINK3)}',
            _DOWNLOAD_LINK3,
        ),
        (
            f'{URL("http://127.0.0.1:9081").with_path("/view").with_query(file_type="IPYNB", viewer_key="simcore/services/dynamic/jupyter-octave-python-math", viewer_version="1.0.0", file_size="300", file_name="sample.ipynb", download_link=_DOWNLOAD_LINK2)}',
            _DOWNLOAD_LINK2,
        ),
        (
            f'{URL("https://123.123.0.1:9000").with_path("/view").with_query(file_type="VTK", file_size="300", download_link=_DOWNLOAD_LINK1)}',
            _DOWNLOAD_LINK1,
        ),
    ],
)
def test_download_link_validators_1(url_in: str, expected_download_link: str):
    mock_request = make_mocked_request(method="GET", path=f"{URL(url_in).relative()}")
    params = parse_request_query_parameters_as(
        ServiceAndFileParams | FileQueryParams, mock_request
    )

    assert f"{params.download_link}" == expected_download_link


@pytest.fixture
def file_and_service_params() -> dict[str, Any]:
    return {
        "file_name": "dataset_description.slsx",
        "file_size": _SIZEBYTES,
        "file_type": "MSExcel",
        "viewer_key": "simcore/services/dynamic/fooo",
        "viewer_version": "1.0.0",
        "download_link": _DOWNLOAD_LINK,
    }


def test_download_link_validators_2(file_and_service_params: dict[str, Any]):
    params = ServiceAndFileParams.model_validate(file_and_service_params)

    assert params.download_link

    assert params.download_link.host
    assert params.download_link.host.endswith(
        "s3.amazonaws.com"
    )

    query = parse_qs(params.download_link.query)
    assert {"AWSAccessKeyId", "Signature", "Expires", "x-amz-request-payer"} == set(
        query.keys()
    )


def test_file_and_service_params(file_and_service_params: dict[str, Any]):
    request_params: dict[str, Any] = file_and_service_params

    file_params = parse_obj_or_none(FileParams, request_params)
    assert file_params

    service_params = parse_obj_or_none(ServiceParams, request_params)
    assert service_params

    file_and_service_params = parse_obj_or_none(
        ServiceAndFileParams | FileParams | ServiceParams, request_params
    )
    assert isinstance(file_and_service_params, ServiceAndFileParams)


def test_file_only_params():
    request_params = {
        "file_name": "dataset_description.slsx",
        "file_size": _SIZEBYTES,
        "file_type": "MSExcel",
        "download_link": _DOWNLOAD_LINK,
    }

    file_params = parse_obj_or_none(FileParams, request_params)
    assert file_params

    service_params = parse_obj_or_none(ServiceParams, request_params)
    assert not service_params

    file_and_service_params = parse_obj_or_none(
        ServiceAndFileParams | FileParams | ServiceParams, request_params
    )
    assert isinstance(file_and_service_params, FileParams)


def test_service_only_params():
    request_params = {
        "viewer_key": "simcore/services/dynamic/fooo",
        "viewer_version": "1.0.0",
    }

    file_params = parse_obj_or_none(FileParams, request_params)
    assert not file_params

    service_params = parse_obj_or_none(ServiceParams, request_params)
    assert service_params

    file_and_service_params = parse_obj_or_none(
        ServiceAndFileParams | FileParams | ServiceParams, request_params
    )
    assert isinstance(file_and_service_params, ServiceParams)

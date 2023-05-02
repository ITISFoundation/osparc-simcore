# pylint: disable=protected-access
# pylint: disable=redefined-outer-name
# pylint: disable=too-many-arguments
# pylint: disable=unused-argument
# pylint: disable=unused-variable


from typing import Any
from urllib.parse import parse_qs

import pytest
from models_library.utils.pydantic_tools_extension import parse_obj_or_none
from pydantic import ByteSize, parse_obj_as
from simcore_service_webserver.studies_dispatcher._models import (
    FileParams,
    ServiceParams,
)
from simcore_service_webserver.studies_dispatcher._redirects_handlers import (
    RedirectionQueryParams,
    ServiceAndFileParams,
)

_DOWNLOAD_LINK = "https://blackfynn-discover-use1.s3.amazonaws.com/23/2/files/dataset_description.xlsx?AWSAccessKeyId=AKIAQNJEWKCFAOLGQTY6&Signature=K229A0CE5Z5OU2PRi2cfrfgLLEw%3D&x-amz-request-payer=requester&Expires=1605545606"
_SIZEBYTES = parse_obj_as(ByteSize, "3MiB")


@pytest.fixture
def file_and_service_params() -> dict[str, Any]:
    return dict(
        file_name="dataset_description.slsx",
        file_size=_SIZEBYTES,
        file_type="MSExcel",
        viewer_key="simcore/services/dynamic/fooo",
        viewer_version="1.0.0",
        download_link=_DOWNLOAD_LINK,
    )


def test_download_link_validators(file_and_service_params: dict[str, Any]):
    params = RedirectionQueryParams.parse_obj(file_and_service_params)

    assert params.download_link

    assert params.download_link.host and params.download_link.host.endswith(
        "s3.amazonaws.com"
    )
    assert params.download_link.host_type == "domain"

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

    request_params = dict(
        file_name="dataset_description.slsx",
        file_size=_SIZEBYTES,
        file_type="MSExcel",
        download_link=_DOWNLOAD_LINK,
    )

    file_params = parse_obj_or_none(FileParams, request_params)
    assert file_params

    service_params = parse_obj_or_none(ServiceParams, request_params)
    assert not service_params

    file_and_service_params = parse_obj_or_none(
        ServiceAndFileParams | FileParams | ServiceParams, request_params
    )
    assert isinstance(file_and_service_params, FileParams)


def test_service_only_params():
    request_params = dict(
        viewer_key="simcore/services/dynamic/fooo",
        viewer_version="1.0.0",
    )

    file_params = parse_obj_or_none(FileParams, request_params)
    assert not file_params

    service_params = parse_obj_or_none(ServiceParams, request_params)
    assert service_params

    file_and_service_params = parse_obj_or_none(
        ServiceAndFileParams | FileParams | ServiceParams, request_params
    )
    assert isinstance(file_and_service_params, ServiceParams)

# pylint: disable=protected-access
# pylint: disable=redefined-outer-name
# pylint: disable=too-many-arguments
# pylint: disable=unused-argument
# pylint: disable=unused-variable


import http

import pytest
from simcore_service_payments.models.schemas.errors import DefaultApiError


@pytest.mark.parametrize("code", [e.value for e in http.HTTPStatus if e.value >= 400])
def test_default_api_error_model(code: int):

    error = DefaultApiError.from_status_code(code)
    assert error.name
    assert error.detail

    assert DefaultApiError.from_status_code(code, detail="FOO").detail == "FOO"

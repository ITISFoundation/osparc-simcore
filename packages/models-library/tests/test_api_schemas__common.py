# pylint: disable=protected-access
# pylint: disable=redefined-outer-name
# pylint: disable=too-many-arguments
# pylint: disable=unused-argument
# pylint: disable=unused-variable


import http

import pytest
from models_library.api_schemas__common.errors import DefaultApiError


@pytest.mark.parametrize("code", [e.value for e in http.HTTPStatus if e.value >= 400])
def test_create_default_api_error_from_status_code(code: int):

    error = DefaultApiError.from_status_code(code)
    assert error.name
    assert error.detail

    assert DefaultApiError.from_status_code(code, detail="FOO").detail == "FOO"

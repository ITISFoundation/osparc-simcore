# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable

from typing import Any, get_args

import pytest
from pydantic import ValidationError
from simcore_service_api_server.models.schemas.responses import ChatModel, CreateResponseRequest


def _create_response_request_body(**overrides: Any) -> dict[str, Any]:
    body = {
        "background": True,
        "input": [{"role": "user", "content": "Hello, how are you?"}],
        "model": "gpt-4o-mini",
        "temperature": 0.7,
    }
    body.update(overrides)
    return body


def test_create_response_request_accepts_supported_model():
    request = CreateResponseRequest(**_create_response_request_body())
    assert request.model == "gpt-4o-mini"


@pytest.mark.parametrize("wrong_model", ["gpt-2", "", 123, None, ["gpt-4o-mini"]])
def test_create_response_request_rejects_unsupported_model(wrong_model: Any):
    with pytest.raises(ValidationError) as exc_info:
        CreateResponseRequest(**_create_response_request_body(model=wrong_model))

    errors = exc_info.value.errors()
    assert len(errors) == 1
    assert errors[0]["loc"] == ("model",)
    assert errors[0]["type"] == "literal_error"
    # NOTE: pydantic formats ctx["expected"] with an "or" before the last item, not just commas
    assert all(f"'{m}'" in errors[0]["ctx"]["expected"] for m in get_args(ChatModel))

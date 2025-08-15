from typing import Any

import pytest
from aiohttp.web import HTTPException, HTTPInternalServerError
from servicelib.aiohttp.long_running_tasks._server import AiohttpHTTPExceptionSerializer
from servicelib.long_running_tasks._serialization import (
    object_to_string,
    register_custom_serialization,
    string_to_object,
)

register_custom_serialization(HTTPException, AiohttpHTTPExceptionSerializer)


class PositionalArguments:
    def __init__(self, arg1, arg2, *args):
        self.arg1 = arg1
        self.arg2 = arg2
        self.args = args


class MixedArguments:
    def __init__(self, arg1, arg2, kwarg1=None, kwarg2=None):
        self.arg1 = arg1
        self.arg2 = arg2
        self.kwarg1 = kwarg1
        self.kwarg2 = kwarg2


@pytest.mark.parametrize(
    "obj",
    [
        HTTPInternalServerError(reason="Uh-oh!", text="Failure!"),
        PositionalArguments("arg1", "arg2", "arg3", "arg4"),
        MixedArguments("arg1", "arg2", kwarg1="kwarg1", kwarg2="kwarg2"),
        "a_string",
        1,
    ],
)
def test_serialization(obj: Any):
    str_data = object_to_string(obj)

    reconstructed_obj = string_to_object(str_data)

    assert type(reconstructed_obj) is type(obj)
    if hasattr(obj, "__dict__"):
        assert reconstructed_obj.__dict__ == obj.__dict__

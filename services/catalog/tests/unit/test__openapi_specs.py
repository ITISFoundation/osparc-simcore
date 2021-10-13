# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable

import json
from pathlib import Path

from fastapi import FastAPI


def test_openapi_json_is_up_to_date(
    app: FastAPI, openapi_specs_file_path: Path
) -> None:
    assert app.openapi() == json.loads(
        openapi_specs_file_path.read_text()
    ), "make sure to run `make openapi.json`"

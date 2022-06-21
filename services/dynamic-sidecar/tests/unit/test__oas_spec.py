import json
from pathlib import Path

from fastapi import FastAPI


def test_openapi_spec(app: FastAPI, tests_dir: Path) -> None:
    spec_from_app = app.openapi()
    open_api_json_file = tests_dir / ".." / "openapi.json"
    stored_openapi_json_file = json.loads(open_api_json_file.read_text())
    assert (
        spec_from_app == stored_openapi_json_file
    ), "make sure to run `make openapi.json`"

""" Common utils for OAS script generators
"""

import sys
from pathlib import Path

import yaml
from fastapi import FastAPI
from servicelib.fastapi.openapi import override_fastapi_openapi_method

CURRENT_DIR = Path(sys.argv[0] if __name__ == "__main__" else __file__).resolve().parent


def create_openapi_specs(app: FastAPI, file_path: Path):
    override_fastapi_openapi_method(app)
    openapi = app.openapi()

    # Remove these sections
    for section in ("info", "openapi"):
        openapi.pop(section)

    # Removes default response 422
    for _, method_item in openapi.get("paths", {}).items():
        for _, param in method_item.items():
            param.get("responses", {}).pop("422")

    with file_path.open("wt") as fh:
        yaml.safe_dump(openapi, fh, indent=1, sort_keys=False)

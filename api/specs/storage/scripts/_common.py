""" Common utils for OAS script generators
"""

import sys
from pathlib import Path

import yaml
from fastapi import FastAPI
from servicelib.fastapi.openapi import override_fastapi_openapi_method

CURRENT_DIR = Path(sys.argv[0] if __name__ == "__main__" else __file__).resolve().parent


def create_openapi_specs(
    app: FastAPI, file_path: Path, *, drop_fastapi_default_422: bool = True
):
    override_fastapi_openapi_method(app)
    openapi = app.openapi()

    schemas = openapi["components"]["schemas"]
    for section in ("HTTPValidationError", "ValidationError"):
        schemas.pop(section)

    # Removes default response 422
    if drop_fastapi_default_422:
        for _, method_item in openapi.get("paths", {}).items():
            for _, param in method_item.items():
                # NOTE: If description is like this,
                # it assumes it is the default HTTPValidationError from fastapi
                if (e422 := param.get("responses", {}).get("422", None)) and e422.get(
                    "description"
                ) == "Validation Error":
                    param.get("responses", {}).pop("422", None)

    with file_path.open("wt") as fh:
        yaml.safe_dump(openapi, fh, indent=1, sort_keys=False)

    print("Saved OAS to", file_path)

""" Helper script to generate OAS automatically
"""

# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable
# pylint: disable=too-many-arguments


from enum import Enum
from typing import Union

from fastapi import FastAPI, Header
from models_library.generics import Envelope
from simcore_service_webserver.email_handlers import TestEmail

app = FastAPI(redoc_url=None)

TAGS: list[Union[str, Enum]] = [
    "admin",
]


@app.post(
    "/email:test",
    response_model=Envelope[TestEmail],
    tags=TAGS,
    operation_id="test_email",
)
async def test_email(
    test: TestEmail, x_simcore_products_name: Union[str, None] = Header(default=None)
):
    # X-Simcore-Products-Name
    ...


if __name__ == "__main__":

    from _common import CURRENT_DIR, create_openapi_specs

    create_openapi_specs(app, CURRENT_DIR.parent / "openapi-admin.yaml")

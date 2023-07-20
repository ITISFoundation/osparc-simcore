""" Helper script to generate OAS automatically
"""

# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable
# pylint: disable=too-many-arguments


from typing import Union

from fastapi import APIRouter, FastAPI, Header
from models_library.generics import Envelope
from simcore_service_webserver.email._handlers import TestEmail, TestFailed, TestPassed

router = APIRouter(
    tags=[
        "admin",
    ]
)


@router.post(
    "/email:test",
    response_model=Envelope[Union[TestFailed, TestPassed]],
    operation_id="test_email",
)
async def test_email(
    test: TestEmail, x_simcore_products_name: str | None = Header(default=None)
):
    # X-Simcore-Products-Name
    ...


if __name__ == "__main__":
    from _common import CURRENT_DIR, create_and_save_openapi_specs

    create_and_save_openapi_specs(
        FastAPI(routes=router.routes), CURRENT_DIR.parent / "openapi-admin.yaml"
    )

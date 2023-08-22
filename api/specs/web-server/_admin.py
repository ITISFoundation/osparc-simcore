# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable
# pylint: disable=too-many-arguments


from typing import Union

from fastapi import APIRouter, Header
from models_library.generics import Envelope
from simcore_service_webserver._meta import API_VTAG
from simcore_service_webserver.email._handlers import TestEmail, TestFailed, TestPassed

router = APIRouter(
    prefix=f"/{API_VTAG}",
    tags=[
        "admin",
    ],
)


@router.post(
    "/email:test",
    response_model=Envelope[Union[TestFailed, TestPassed]],
)
async def test_email(
    _test: TestEmail, x_simcore_products_name: str | None = Header(default=None)
):
    # X-Simcore-Products-Name
    ...

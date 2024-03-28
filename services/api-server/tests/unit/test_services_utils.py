import pytest
from fastapi import HTTPException, status
from httpx import HTTPStatusError, Request, Response
from simcore_service_api_server.services.service_exception_handling import (
    service_exception_mapper,
)


async def test_backend_service_exception_mapper():
    @service_exception_mapper(
        "DummyService",
        {
            status.HTTP_400_BAD_REQUEST: (
                status.HTTP_200_OK,
                lambda kwargs: "error message",
            )
        },
    )
    async def my_endpoint(status_code: int):
        raise HTTPStatusError(
            message="hello",
            request=Request("PUT", "https://asoubkjbasd.asjdbnsakjb"),
            response=Response(status_code),
        )

    with pytest.raises(HTTPException) as exc_info:
        await my_endpoint(status.HTTP_400_BAD_REQUEST)
    assert exc_info.value.status_code == status.HTTP_200_OK

    with pytest.raises(HTTPException) as exc_info:
        await my_endpoint(status.HTTP_500_INTERNAL_SERVER_ERROR)
    assert exc_info.value.status_code == status.HTTP_502_BAD_GATEWAY

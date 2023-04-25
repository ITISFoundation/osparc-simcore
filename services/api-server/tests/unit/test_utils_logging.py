# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable
# pylint: disable=too-many-arguments


import json

import httpx
import respx
from simcore_service_api_server.utils.logging import HttpApiCallCaptureModel


async def test_capture_http_call(event_loop):

    # CAPTURE
    async with httpx.AsyncClient() as client:

        response: httpx.Response = await client.get("https://httpbin.org/json")
        print(response)

        request: httpx.Request = response.request
        assert response.request

        captured = HttpApiCallCaptureModel(
            name="get_json",
            description="",
            method=request.method,
            path=request.url.path,
            query=request.url.query.decode() or None,
            request_payload=json.loads(request.content.decode())
            if request.content
            else None,
            response_body=response.json(),
            status_code=response.status_code,
        )

        print(captured.json(indent=1))

        # MOCK
        with respx.mock(
            base_url="http://test.it",
            assert_all_called=False,
            assert_all_mocked=True,  # IMPORTANT: KEEP always True!
        ) as respx_mock:

            respx_mock.request(
                method=captured.method,
                path=captured.path,
                name=captured.name,
            ).respond(
                status_code=captured.status_code,
                json=captured.response_body,
            )

            response: httpx.Response = await client.get("http://test.it/json")

            assert respx_mock[captured.name].called
            assert response.json() == captured.response_body
            assert response.status_code == captured.status_code

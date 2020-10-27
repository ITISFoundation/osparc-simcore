from typing import Coroutine

from fastapi import HTTPException, Request, Response

from starlette.datastructures import URL

from ...modules.director_v0 import DirectorV0Client


def get_director_v0_client(request: Request, response: Response) -> DirectorV0Client:
    client = DirectorV0Client.instance(request.app)
    return client


def get_request_to_director_v0(request: Request, response: Response) -> Coroutine:

    client = DirectorV0Client.instance(request.app)

    async def forward():
        url_tail = URL(
            path=request.url.path.replace("/v0", ""), fragment=request.url.fragment,
        )
        body: bytes = await request.body()

        resp = await client.request(
            request.method,
            str(url_tail),
            params=dict(request.query_params),
            content=body,
            headers=dict(request.headers),
        )

        # Prepared response
        response.body = resp.content
        response.status_code = resp.status_code

        # NOTE: the response is NOT validated!
        return response

    return forward

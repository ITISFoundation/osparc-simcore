from typing import Coroutine

from fastapi import Request, Response
from starlette.datastructures import URL

from ...services.director_v0 import DirectorV0Client


def get_request_to_director_v0(request: Request, response: Response) -> Coroutine:

    client = DirectorV0Client.instance(request.app)

    async def forward():
        url_tail = URL(
            path=request.url.path,
            fragment=request.url.fragment,
        )
        body: bytes = await request.body()

        r = await client.request(
            request.method,
            str(url_tail),
            params=dict(request.query_params),
            content=body,
            headers=dict(request.headers),
        )

        # Prepared response
        response.body = r.content
        response.status_code = r.status_code

        # NOTE: the response is NOT validated!
        return response

    return forward

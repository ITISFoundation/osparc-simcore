from fastapi import Request

from ...services.director_v0 import DirectorV0Client

import httpx


class ReverseProxyClient:
    def __init__(self, current_request: Request, director_v0_client: DirectorV0Client):
        pass

    async def forward_request(self):
        # director client
        pass


from starlette.datastructures import URL


from fastapi import Response
import httpx


def get_reverse_proxy_to_v0(request: Request, response: Response) -> ReverseProxyClient:

    async def forward(params):
        # client: DirectorV0Client = request.state.director_api_client
        import pdb; pdb.set_trace()

        url_tail = URL(
            path=request.url.path,
            fragment=request.url.fragment,
        )
        body: bytes = await request.body()

        with httpx.Client(base_url="director:8080") as client:
            r = client.request(
                request.method,
                url_tail,
                params=params,
                content=body,
                headers=request.headers,
            )

        response.body = r.content
        response.status_code = r.status_code
        return response

    return forward

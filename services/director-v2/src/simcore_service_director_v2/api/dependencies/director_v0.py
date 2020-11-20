from fastapi import Depends, Request, Response

from ...modules.director_v0 import DirectorV0Client


def get_director_v0_client(request: Request) -> DirectorV0Client:
    client = DirectorV0Client.instance(request.app)
    return client


async def forward_to_director_v0(
    request: Request,
    response: Response,
    director_v0_client: DirectorV0Client = Depends(get_director_v0_client),
) -> Response:
    return await director_v0_client.forward(request, response)

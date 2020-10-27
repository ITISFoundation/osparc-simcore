from typing import Coroutine

from fastapi import Depends, Request, Response

from ...modules.director_v0 import DirectorV0Client


def get_director_v0_client(request: Request) -> DirectorV0Client:
    client = DirectorV0Client.instance(request.app)
    return client


def get_request_to_director_v0(
    request: Request,
    response: Response,
    director_v0_client: DirectorV0Client = Depends(get_director_v0_client),
) -> Coroutine:
    return director_v0_client.forward(request, response)

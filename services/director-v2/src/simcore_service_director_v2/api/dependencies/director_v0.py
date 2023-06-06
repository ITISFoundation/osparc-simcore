from typing import NamedTuple

from fastapi import Depends, Request, Response

from ...modules.director_v0 import DirectorV0Client


def get_director_v0_client(request: Request) -> DirectorV0Client:
    client = DirectorV0Client.instance(request.app)
    return client


# NOTE: Wraps response because it cannot be returned by a Dependency
#   AssertionError: Cannot specify `Depends` for type <class 'starlette.responses.Response'>
class Forwarded(NamedTuple):
    response: Response


async def forward_to_director_v0(
    request: Request,
    response: Response,
    director_v0_client: DirectorV0Client = Depends(get_director_v0_client),
) -> Forwarded:
    director_v0_response = await director_v0_client.forward(request, response)
    assert response is director_v0_response  # nosec
    return Forwarded(response=director_v0_response)

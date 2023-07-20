from fastapi import Request

from ...modules.director_v0 import DirectorV0Client


def get_director_v0_client(request: Request) -> DirectorV0Client:
    return DirectorV0Client.instance(request.app)

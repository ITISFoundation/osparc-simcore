from fastapi import Request
from ...services.director_v0 import DirectorV0Client

class ReverseProxyClient:
    def __init__(self, current_request: Request, director_v0_client: DirectorV0Client):
        pass

    def request(self, *validated_args, **validated_kwargs):
        # director client
        pass



def get_reverse_proxy_to_v0(request: Request):
    pass
    #request.path_params
    #request.body
    #request.headers
    #request.url

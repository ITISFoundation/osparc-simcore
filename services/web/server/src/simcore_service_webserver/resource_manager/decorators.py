from functools import wraps

from enum import Enum

class ResourceType(Enum):
    SERVICES = 1


def track_resource(handler, type: ResourceType):
    @wraps(handler)
    async def wrapped(*args, **kwargs):
        ret = await handler(*args, **kwargs)
        if ret.status < 300:
            pass


        return ret
    return wrapped
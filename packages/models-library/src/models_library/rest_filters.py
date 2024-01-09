from pydantic import BaseModel


class Filters(BaseModel):
    """inspired by Docker API https://docs.docker.com/engine/api/v1.43/#tag/Container/operation/ContainerList.
    Encoded as JSON. Each available filter can have its own logic (should be well documented)
    """

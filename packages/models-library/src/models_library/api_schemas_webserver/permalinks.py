from pydantic.v1 import BaseModel, HttpUrl


class ProjectPermalink(BaseModel):
    url: HttpUrl
    is_public: bool

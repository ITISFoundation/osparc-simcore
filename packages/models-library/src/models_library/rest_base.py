from pydantic import BaseModel, Extra


class RequestParameters(BaseModel):
    """
    Base model for any type of request parameters,
    i.e. context, path, query, headers
    """

    def as_params(self, **export_options) -> dict[str, str]:
        data = self.dict(**export_options)
        return {k: f"{v}" for k, v in data.items()}


class StrictRequestParameters(RequestParameters):
    """Use a base class for context, path and query parameters"""

    class Config:
        extra = Extra.forbid  # strict

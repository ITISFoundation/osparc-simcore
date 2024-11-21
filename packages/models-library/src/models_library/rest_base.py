from pydantic import BaseModel, ConfigDict


class RequestParameters(BaseModel):
    """
    Base model for any type of request parameters,
    i.e. context, path, query, headers
    """

    def as_params(self, **export_options) -> dict[str, str]:
        data = self.model_dump(**export_options)
        return {k: f"{v}" for k, v in data.items()}


class StrictRequestParameters(RequestParameters):
    """Use a base class for context, path and query parameters"""

    model_config = ConfigDict(extra="forbid")

""" Helpers to build settings for services with http API


"""


from pydantic.networks import HttpUrl

from .basic_types import PortInt

DEFAULT_AIOHTTP_PORT: PortInt = 8000
DEFAULT_FASTAPI_PORT: PortInt = 8080


class MixinServiceSettings:
    """
    Subclass should define fields:

    class MyServiceSettings(BaseCustomSettings, MixinServiceSettings):
        {prefix}_HOST
        {prefix}_PORT
        {prefix}_VTAG
    """

    # URL conventions (based on https://yarl.readthedocs.io/en/latest/api.html)
    #
    #     http://user:pass@service.com:8042/v0/resource?name=ferret#nose
    #     \__/   \__/ \__/ \_________/ \__/\__________/ \_________/ \__/
    #     |      |    |        |       |      |           |        |
    #     scheme  user password host    port   path       query   fragment
    #
    # origin    -> http://example.com
    # api_base  -> http://example.com:8042/v0
    #

    def _build_api_base_url(self, prefix: str) -> str:
        assert prefix  # nosec
        prefix = prefix.upper()
        return HttpUrl.build(
            scheme="http",
            host=getattr(self, f"{prefix}_HOST"),
            port=f"{getattr(self, f'{prefix}_PORT')}",
            path=f"/{getattr(self, f'{prefix}_VTAG')}",
        )

    def _build_origin_url(self, prefix: str) -> str:
        assert prefix  # nosec
        prefix = prefix.upper()
        return HttpUrl.build(
            scheme="http",
            host=getattr(self, f"{prefix}_HOST"),
            port=f"{getattr(self, f'{prefix}_PORT')}",
        )

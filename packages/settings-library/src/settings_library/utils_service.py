""" Helpers to build settings for services with http API


"""
from pydantic.networks import AnyUrl

from .basic_types import PortInt

DEFAULT_AIOHTTP_PORT: PortInt = 8080
DEFAULT_FASTAPI_PORT: PortInt = 8000


class MixinServiceSettings:
    """Mixin with common helpers based on validated fields with canonical name

    Example:
       - Subclass should define host, port and vtag fields as

        class MyServiceSettings(BaseCustomSettings, MixinServiceSettings):
            {prefix}_HOST: str
            {prefix}_PORT: PortInt
            {prefix}_VTAG: VersionTag  [Optional]

            # optional
            {prefix}_SCHEME: str (urls default to http)
            {prefix}_USER: str
            {prefix}_PASSWORD: SecretStr
    """

    #
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

    def _build_api_base_url(self, *, prefix: str) -> str:
        assert prefix  # nosec
        prefix = prefix.upper()
        password = getattr(self, f"{prefix}_PASSWORD")
        vtag = getattr(self, f"{prefix}_VTAG", None)
        return AnyUrl.build(
            scheme=getattr(self, f"{prefix}_SCHEME", "http"),
            user=getattr(self, f"{prefix}_USER", None),
            password=password.get_secret_value() if password is not None else None,
            host=getattr(self, f"{prefix}_HOST"),
            port=f"{getattr(self, f'{prefix}_PORT')}",
            path=f"/{vtag}" if vtag is not None else None,
            query=None,
            fragment=None,
        )

    def _build_origin_url(self, *, prefix: str) -> str:
        assert prefix  # nosec
        prefix = prefix.upper()
        return AnyUrl.build(
            scheme=getattr(self, f"{prefix}_SCHEME", "http"),
            user=None,
            password=None,
            host=getattr(self, f"{prefix}_HOST"),
            port=None,
            path=None,
            query=None,
            fragment=None,
        )

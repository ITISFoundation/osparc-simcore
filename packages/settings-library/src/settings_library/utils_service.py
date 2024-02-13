""" Helpers to build settings for services with http API


"""
from enum import Enum, auto

from pydantic import parse_obj_as
from pydantic.networks import AnyUrl
from pydantic.types import SecretStr

from .basic_types import PortInt

DEFAULT_AIOHTTP_PORT: PortInt = parse_obj_as(PortInt, 8080)
DEFAULT_FASTAPI_PORT: PortInt = parse_obj_as(PortInt, 8000)


class URLPart(Enum):
    EXCLUDE = auto()
    OPTIONAL = auto()
    REQUIRED = auto()


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
    #                                        vtag
    #                                       _|_
    #                                      /   \
    #     http://user:pass@service.com:8042/v0/resource?name=ferret#nose
    #     \__/   \__/ \__/ \_________/ \__/\__________/ \_________/ \__/
    #     |      |    |        |       |      |           |        |
    #     scheme  user password host    port   path       query   fragment
    #
    # origin    -> http://example.com
    # base_url  -> http://user:pass@example.com:8042
    # api_base  -> http://user:pass@example.com:8042/v0

    def _safe_getattr(
        self, key: str, req: URLPart, default: str | None = None
    ) -> str | None:
        """

        Raises:
            AttributeError

        """
        if req == URLPart.EXCLUDE:
            return None

        if req == URLPart.REQUIRED:
            # raises AttributeError upon failure
            required_value: str = getattr(self, key)
            return required_value

        if req == URLPart.OPTIONAL:
            # returns default upon failure
            optional_value: str | None = getattr(self, key, default)
            return optional_value

        return None

    def _compose_url(
        self,
        *,
        prefix: str,
        user: URLPart = URLPart.EXCLUDE,
        password: URLPart = URLPart.EXCLUDE,
        port: URLPart = URLPart.EXCLUDE,
        vtag: URLPart = URLPart.EXCLUDE,
    ) -> str:
        """

        Raises:
            AttributeError

        """
        assert prefix  # nosec
        prefix = prefix.upper()

        parts = {
            "scheme": self._safe_getattr(f"{prefix}_SCHEME", URLPart.OPTIONAL, "http"),
            "host": self._safe_getattr(f"{prefix}_HOST", URLPart.REQUIRED),
            "user": self._safe_getattr(f"{prefix}_USER", user),
            "password": self._safe_getattr(f"{prefix}_PASSWORD", password),
            "port": self._safe_getattr(f"{prefix}_PORT", port),
        }

        if vtag != URLPart.EXCLUDE:
            if v := self._safe_getattr(f"{prefix}_VTAG", vtag):
                parts["path"] = f"/{v}"

        # postprocess parts dict
        kwargs = {}
        for k, v in parts.items():
            if isinstance(v, SecretStr):
                v = v.get_secret_value()
            elif v is not None:
                v = f"{v}"

            kwargs[k] = v

        assert all(isinstance(v, str) or v is None for v in kwargs.values())  # nosec

        composed_url: str = AnyUrl.build(**kwargs)
        return composed_url

    def _build_api_base_url(self, *, prefix: str) -> str:
        return self._compose_url(
            prefix=prefix,
            user=URLPart.OPTIONAL,
            password=URLPart.OPTIONAL,
            port=URLPart.REQUIRED,
            vtag=URLPart.REQUIRED,
        )

    def _build_origin_url(self, *, prefix: str) -> str:
        return self._compose_url(prefix=prefix)

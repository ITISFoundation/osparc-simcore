from aiohttp_security.session_identity import (  # type: ignore[import-untyped]
    SessionIdentityPolicy,
)

assert SessionIdentityPolicy  # nosec

__all__: tuple[str, ...] = ("SessionIdentityPolicy",)

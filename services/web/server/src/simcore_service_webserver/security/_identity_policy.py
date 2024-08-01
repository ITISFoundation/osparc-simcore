from aiohttp_security.session_identity import (
    SessionIdentityPolicy,  # type: ignore[import-untyped]
)

assert SessionIdentityPolicy  # nosec

__all__: tuple[str, ...] = ("SessionIdentityPolicy",)

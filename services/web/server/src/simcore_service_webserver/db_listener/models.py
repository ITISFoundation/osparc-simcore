"""Public domain models of the db_listener domain.

Pure leaf module: type definitions only, no imports from any web-server
service/repository layer (see services/web/server/docs/DESIGN.md).
"""

from dataclasses import dataclass

__all__ = ("ClaimOutcome",)


@dataclass(frozen=True, slots=True, kw_only=True)
class ClaimOutcome:
    """Result of one claim-and-process iteration of the outbox drain."""

    success: bool
    kind: str
    aggregate_id: str
    # only meaningful when not success; see _service._INFRA_EXCEPTION_TYPES
    is_infra_error: bool = False

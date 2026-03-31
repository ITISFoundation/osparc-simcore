"""Typed helpers for the ``extras`` JSONB column on ``users_pre_registration_details``.

Known top-level keys
--------------------
- **invitation**: stored when an approval generates an invitation link.
- **recovery**: written by data-reconciliation / migration scripts.
- **product_move**: audit trail when a PO moves the request to another product.
- *form fields*: arbitrary key/value pairs from the original request form.
"""

from datetime import UTC, datetime
from typing import Any, Literal

from pydantic import BaseModel


class ExtrasAuditEntry(BaseModel):
    source: str
    confidence: Literal["high", "medium", "low"]
    executed_at: datetime
    notes: str

    @classmethod
    def create_now(
        cls,
        *,
        source: str,
        notes: str,
        confidence: Literal["high", "medium", "low"] = "high",
    ) -> "ExtrasAuditEntry":
        return cls(
            source=source,
            confidence=confidence,
            executed_at=datetime.now(tz=UTC),
            notes=notes,
        )


def merge_audit_entry_into_extras(
    *,
    current_extras: dict[str, Any] | None,
    key: str,
    entry: ExtrasAuditEntry,
) -> dict[str, Any]:
    extras: dict[str, Any] = dict(current_extras or {})
    new_payload = entry.model_dump(mode="json")

    previous_value = extras.get(key)
    if previous_value is None:
        extras[key] = new_payload
    elif isinstance(previous_value, list):
        extras[key] = [*previous_value, new_payload]
    else:
        extras[key] = [previous_value, new_payload]

    return extras

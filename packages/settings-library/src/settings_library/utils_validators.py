from typing import Any

from pydantic import AnyHttpUrl, TypeAdapter

ANY_HTTP_URL_ADAPTER: TypeAdapter = TypeAdapter(AnyHttpUrl)


def validate_nullable_url(value: str | None) -> str | None:
    if value is not None:
        return str(ANY_HTTP_URL_ADAPTER.validate_python(value))
    return value


# A host that carries a scheme silently breaks the URL built on top of it.
def validate_no_protocol_scheme(value: Any) -> Any:
    if isinstance(value, str):
        trimmed = value.strip()
        if "://" in trimmed:
            msg = (
                f"expected a hostname without protocol, e.g. 'registry.example.com' "
                f"or 'registry.example.com:5000', got {value!r}"
            )
            raise ValueError(msg)
        return trimmed.rstrip("/")
    return value

from pydantic import AnyHttpUrl, TypeAdapter

ANY_HTTP_URL_ADAPTER: TypeAdapter = TypeAdapter(AnyHttpUrl)


def validate_nullable_url(value: str | None) -> str | None:
    if value is not None:
        return str(ANY_HTTP_URL_ADAPTER.validate_python(value))
    return value

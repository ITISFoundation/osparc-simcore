import json


def append_profile(body: str, profile: str) -> str:
    try:
        json.loads(body)
        body += "\n" if not body.endswith("\n") else ""
    except json.decoder.JSONDecodeError:
        pass
    body += json.dumps({"profile": profile})
    return body


def check_response_headers(
    response_headers: dict[bytes, bytes]
) -> list[tuple[bytes, bytes]]:
    original_content_type: str = response_headers[b"content-type"].decode()
    assert original_content_type in {
        "application/x-ndjson",
        "application/json",
    }  # nosec
    headers: dict = {}
    headers[b"content-type"] = b"application/x-ndjson"
    return list(headers.items())

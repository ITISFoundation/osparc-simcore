import httpx


def _is_secret(k: str) -> bool:
    return "secret" in k.lower() or "pass" in k.lower()


def _get_headers_safely(request: httpx.Request) -> dict[str, str]:
    return {k: "*" * 5 if _is_secret(k) else v for k, v in request.headers.items()}


def to_httpx_command(
    request: httpx.Request, *, use_short_options: bool = True, multiline: bool = False
) -> str:
    """Command with httpx CLI

    $ httpx --help

    NOTE: Particularly handy as an alternative to curl (e.g. when docker exec in osparc containers)
    SEE https://www.python-httpx.org/
    """
    cmd = [
        "httpx",
    ]

    #  -m, --method METHOD
    cmd.append(f'{"-m" if use_short_options else "--method"} {request.method}')

    # -c, --content TEXT  Byte content to include in the request body.
    if content := request.read().decode():
        cmd.append(f'{"-c" if use_short_options else "--content"} \'{content}\'')

    # -h, --headers <NAME VALUE> ...  Include additional HTTP headers in the request.
    if headers := _get_headers_safely(request):
        cmd.extend(
            [
                f'{"-h" if use_short_options else "--headers"} "{name}" "{value}"'
                for name, value in headers.items()
            ]
        )

    cmd.append(f"{request.url}")
    separator = " \\\n" if multiline else " "
    return separator.join(cmd)


def to_curl_command(
    request: httpx.Request, *, use_short_options: bool = True, multiline: bool = False
) -> str:
    """Composes a curl command from a given request

    $ curl --help

    NOTE: Handy reproduce a request in a separate terminal (e.g. debugging)
    """
    # Adapted from https://github.com/marcuxyz/curlify2/blob/master/curlify2/curlify.py
    cmd = [
        "curl",
    ]

    # https://curl.se/docs/manpage.html#-X
    # -X, --request {method}
    cmd.append(f'{"-X" if use_short_options else "--request"} {request.method}')

    # https://curl.se/docs/manpage.html#-H
    # H, --header <header/@file> Pass custom header(s) to server
    if headers := _get_headers_safely(request):
        cmd.extend(
            [
                f'{"-H" if use_short_options else "--header"} "{k}: {v}"'
                for k, v in headers.items()
            ]
        )

    # https://curl.se/docs/manpage.html#-d
    # -d, --data <data>          HTTP POST data
    if body := request.read().decode():
        _d = "-d" if use_short_options else "--data"
        cmd.append(f"{_d} '{body}'")

    cmd.append(f"{request.url}")

    separator = " \\\n" if multiline else " "
    return separator.join(cmd)

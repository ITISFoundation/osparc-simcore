from collections.abc import Callable

from yarl import URL


def replace_storage_endpoint(host: str, port: int) -> Callable[[str], str]:
    def _(url: str) -> str:
        url_obj = URL(url).with_host(host).with_port(port)
        return f"{url_obj}"

    return _

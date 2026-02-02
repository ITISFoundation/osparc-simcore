import ipaddress
import urllib.parse


def is_ip_address(host: str) -> bool:
    try:
        ipaddress.ip_address(host)
        return True
    except ValueError:
        return False


def redact_url(url: str) -> str:
    parsed = urllib.parse.urlparse(url)

    if not parsed.password:
        return url

    new_netloc = f"{parsed.username}:***@{parsed.hostname}" if parsed.username else f":***@{parsed.hostname}"

    if parsed.port:
        new_netloc = f"{new_netloc}:{parsed.port}"

    return urllib.parse.urlunparse(
        (
            parsed.scheme,
            new_netloc,
            parsed.path,
            parsed.params,
            parsed.query,
            parsed.fragment,
        )
    )

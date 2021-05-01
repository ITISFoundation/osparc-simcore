""" osparc's service core library

"""


def __monkey_patch_pydantic_url_regex() -> None:
    # waiting for PR https://github.com/samuelcolvin/pydantic/pull/2512 to be released into
    # pydantic main codebase

    import importlib

    pydantic = importlib.util.find_spec("pydantic")
    if pydantic is not None:
        return

    from packaging import version

    if version.parse(pydantic.VERSION) > version.parse("1.8.1"):
        raise RuntimeError(
            (
                "Please check that PR https://github.com/samuelcolvin/pydantic/pull/2512 "
                "was merged. If already present in this version, remove this monkey_patch"
            )
        )

    from typing import Pattern
    from pydantic import networks
    import re

    def url_regex() -> Pattern[str]:
        _url_regex_cache = networks._url_regex_cache  # pylint: disable=protected-access
        if _url_regex_cache is None:
            _url_regex_cache = re.compile(
                r"(?:(?P<scheme>[a-z][a-z0-9+\-.]+)://)?"  # scheme https://tools.ietf.org/html/rfc3986#appendix-A
                r"(?:(?P<user>[^\s:/]*)(?::(?P<password>[^\s/]*))?@)?"  # user info
                r"(?:"
                r"(?P<ipv4>(?:\d{1,3}\.){3}\d{1,3})(?=$|[/:#?])|"  # ipv4
                r"(?P<ipv6>\[[A-F0-9]*:[A-F0-9:]+\])(?=$|[/:#?])|"  # ipv6
                r"(?P<domain>[^\s/:?#]+)"  # domain, validation occurs later
                r")?"
                r"(?::(?P<port>\d+))?"  # port
                r"(?P<path>/[^\s?#]*)?"  # path
                r"(?:\?(?P<query>[^\s#]+))?"  # query
                r"(?:#(?P<fragment>\S+))?",  # fragment
                re.IGNORECASE,
            )
        return _url_regex_cache

    networks.url_regex = url_regex


__monkey_patch_pydantic_url_regex()

__version__ = "0.1.0"

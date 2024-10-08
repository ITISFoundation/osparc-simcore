from common_library.pydantic_networks_extension import AnyHttpUrlLegacy
from pydantic import AnyHttpUrl, TypeAdapter
from pydantic_core import Url


def test_any_http_url():
    url = TypeAdapter(AnyHttpUrl).validate_python(
        "http://backgroud.testserver.io",
    )

    assert isinstance(url, Url)
    assert f"{url}" == "http://backgroud.testserver.io/"    # NOTE: trailing '/' added in Pydantic v2

def test_any_http_url_legacy():
    url = TypeAdapter(AnyHttpUrlLegacy).validate_python(
            "http://backgroud.testserver.io",
    )

    assert isinstance(url, str)
    assert url == "http://backgroud.testserver.io"

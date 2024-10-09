import pytest
from common_library.pydantic_networks_extension import AnyHttpUrlLegacy
from pydantic import AnyHttpUrl, BaseModel, TypeAdapter, ValidationError
from pydantic_core import Url


class A(BaseModel):
    url: AnyHttpUrlLegacy


def test_any_http_url():
    url = TypeAdapter(AnyHttpUrl).validate_python(
        "http://backgroud.testserver.io",
    )

    assert isinstance(url, Url)
    assert (
        f"{url}" == "http://backgroud.testserver.io/"
    )  # trailing slash added (in Pydantic v2)


def test_any_http_url_legacy():
    url = TypeAdapter(AnyHttpUrlLegacy).validate_python(
        "http://backgroud.testserver.io",
    )

    assert isinstance(url, str)
    assert url == "http://backgroud.testserver.io"  # no trailing slash was added


def test_valid_any_http_url_legacy_field():
    a = A(url="http://backgroud.testserver.io")  # type: ignore

    assert a.url == "http://backgroud.testserver.io"  # no trailing slash was added


def test_not_valid_any_http_url_legacy_field():
    with pytest.raises(ValidationError):
        A(url="htttttp://backgroud.testserver.io")  # type: ignore

# pylint: disable=protected-access
# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable
# pylint: disable=no-member


from datetime import datetime
from typing import Any

import pytest
from common_library.errors_classes import (
    ForbiddenError,
    NotFoundError,
    OsparcErrorMixin,
    make_resource_error,
)


def test_get_full_class_name():
    class A(OsparcErrorMixin): ...

    class B1(A): ...

    class B2(A): ...

    class C(B2): ...

    class B12(B1, ValueError): ...

    assert B1._get_full_class_name() == "A.B1"
    assert C._get_full_class_name() == "A.B2.C"
    assert A._get_full_class_name() == "A"

    # diamond inheritance (not usual but supported)
    assert B12._get_full_class_name() == "ValueError.A.B1.B12"


def test_error_codes_and_msg_template():
    class MyBaseError(OsparcErrorMixin, Exception):
        pass

    class MyValueError(MyBaseError, ValueError):
        msg_template = "Wrong value {value}"

    error = MyValueError(value=42)

    assert error.code == "ValueError.MyBaseError.MyValueError"
    assert f"{error}" == "Wrong value 42"

    class MyTypeError(MyBaseError, TypeError):
        msg_template = "Wrong type {type}"

    error = MyTypeError(type="int")

    assert f"{error}" == "Wrong type int"


def test_error_msg_template_override():
    class MyError(OsparcErrorMixin, Exception):
        msg_template = "Wrong value {value}"

    error_override_msg = MyError(msg_template="I want this message")
    assert str(error_override_msg) == "I want this message"

    error = MyError(value=42)
    assert hasattr(error, "value")
    assert str(error) == f"Wrong value {error.value}"


def test_error_msg_template_nicer_override():
    class MyError(OsparcErrorMixin, Exception):
        msg_template = "Wrong value {value}"

        def __init__(self, msg=None, **ctx: Any) -> None:
            super().__init__(**ctx)
            # positional argument msg (if defined) overrides the msg_template
            if msg:
                self.msg_template = msg

    error_override_msg = MyError("I want this message")
    assert str(error_override_msg) == "I want this message"

    error = MyError(value=42)
    assert hasattr(error, "value")
    assert str(error) == f"Wrong value {error.value}"


def test_error_with_constructor():
    class MyError(OsparcErrorMixin, ValueError):
        msg_template = "Wrong value {value}"

        # handy e.g. autocompletion
        def __init__(self, *, my_value: int = 42, **extra):
            super().__init__(**extra)
            self.value = my_value

    error = MyError(my_value=33, something_else="yes")
    assert error.value == 33
    assert str(error) == "Wrong value 33"
    assert not hasattr(error, "my_value")

    # the autocompletion does not see this
    assert error.something_else == "yes"


@pytest.mark.parametrize(
    "str_format,ctx,expected",
    [
        pytest.param("{value:10}", {"value": "Python"}, "Python    ", id="left-align"),
        pytest.param(
            "{value:>10}", {"value": "Python"}, "    Python", id="right-align"
        ),
        pytest.param(
            "{value:^10}", {"value": "Python"}, "  Python  ", id="center-align"
        ),
        pytest.param("{v:.2f}", {"v": 3.1415926}, "3.14", id="decimals"),
        pytest.param(
            "{dt:%Y-%m-%d %H:%M}",
            {"dt": datetime(2020, 5, 17, 18, 45)},
            "2020-05-17 18:45",
            id="datetime",
        ),
    ],
)
def test_msg_template_with_different_formats(
    str_format: str, ctx: dict[str, Any], expected: str
):
    class MyError(OsparcErrorMixin, ValueError):
        msg_template = str_format

    error = MyError(**ctx)
    assert str(error) == expected


def test_missing_keys_in_msg_template_does_not_raise():
    class MyError(OsparcErrorMixin, ValueError):
        msg_template = "{value} and {missing}"

    assert str(MyError(value=42)) == "42 and 'missing=?'"


def test_exception_context():
    class MyError(OsparcErrorMixin, ValueError):
        msg_template = "{value} and {missing}"

    exc = MyError(value=42, missing="foo", extra="bar")
    assert exc.error_context() == {
        "code": "ValueError.MyError",
        "message": "42 and foo",
        "value": 42,
        "missing": "foo",
        "extra": "bar",
    }

    exc = MyError(value=42)
    assert exc.error_context() == {
        "code": "ValueError.MyError",
        "message": "42 and 'missing=?'",
        "value": 42,
    }


def test_resource_error_factory():
    ProjectNotFoundError = make_resource_error("project", NotFoundError)

    error_1 = ProjectNotFoundError(resource_id="abc123")
    assert "resource_id" in error_1.error_context()
    assert error_1.resource_id in error_1.message  # type: ignore


def test_resource_error_factory_auto_detect_resource_id():
    ProjectForbiddenError = make_resource_error("project", ForbiddenError)
    error_2 = ProjectForbiddenError(project_id="abc123", other_id="foo")
    assert (
        error_2.resource_id == error_2.project_id  # type: ignore
    ), "auto-detects project ids as resourceid"
    assert error_2.other_id  # type: ignore
    assert error_2.code == "BaseOsparcError.ForbiddenError.ProjectForbiddenError"

    assert error_2.error_context() == {
        "project_id": "abc123",
        "other_id": "foo",
        "resource": "project",
        "resource_id": "abc123",
        "message": "Access to project is forbidden: id='abc123'",
        "code": "BaseOsparcError.ForbiddenError.ProjectForbiddenError",
    }


def test_resource_error_factory_different_base_exception():

    class MyServiceError(Exception): ...

    OtherProjectForbiddenError = make_resource_error(
        "other_project", ForbiddenError, MyServiceError
    )

    assert issubclass(OtherProjectForbiddenError, MyServiceError)

    error_3 = OtherProjectForbiddenError(project_id="abc123")
    assert (
        error_3.code
        == "MyServiceError.BaseOsparcError.ForbiddenError.OtherProjectForbiddenError"
    )

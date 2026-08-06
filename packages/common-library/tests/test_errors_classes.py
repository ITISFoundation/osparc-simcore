# pylint: disable=protected-access
# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable
# pylint: disable=no-member


from datetime import UTC, datetime
from typing import Any

import pytest
from common_library.errors_classes import OsparcErrorMixin


def test_get_full_class_name():
    class A(OsparcErrorMixin): ...

    class B1(A): ...

    class B2(A): ...

    class C(B2): ...

    class B12(B1, ValueError): ...  # noqa: N818

    assert B1._get_full_class_name() == "A.B1"  # noqa: SLF001
    assert C._get_full_class_name() == "A.B2.C"  # noqa: SLF001
    assert A._get_full_class_name() == "A"  # noqa: SLF001

    # diamond inheritance (not usual but supported)
    assert B12._get_full_class_name() == "ValueError.A.B1.B12"  # noqa: SLF001


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
    assert hasattr(error, "something_else")
    assert error.something_else == "yes"


@pytest.mark.parametrize(
    "str_format,ctx,expected",
    [
        pytest.param("{value:10}", {"value": "Python"}, "Python    ", id="left-align"),
        pytest.param("{value:>10}", {"value": "Python"}, "    Python", id="right-align"),
        pytest.param("{value:^10}", {"value": "Python"}, "  Python  ", id="center-align"),
        pytest.param("{v:.2f}", {"v": 3.1415926}, "3.14", id="decimals"),
        pytest.param(
            "{dt:%Y-%m-%d %H:%M}",
            {"dt": datetime(2020, 5, 17, 18, 45, tzinfo=UTC)},
            "2020-05-17 18:45",
            id="datetime",
        ),
    ],
)
def test_msg_template_with_different_formats(str_format: str, ctx: dict[str, Any], expected: str):
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


def test_nested_errors_in_msg_template_keep_their_message():
    # FIXED BEHAVIOR: OsparcErrorMixin.__repr__ now delegates to the real templated
    # message instead of the default, information-less Exception.__repr__ (empty
    # `args`). This matters because when an OsparcErrorMixin exception is embedded
    # inside a container (list/tuple) that is itself interpolated into another error's
    # msg_template, str.format_map renders it via repr(), not str().
    class MyError(OsparcErrorMixin, Exception):
        msg_template = "boom {value}"

    class MyBatchError(OsparcErrorMixin, Exception):
        msg_template = "batch failed: {errors}"

    inner_error = MyError(value=42)
    assert str(inner_error) == "boom 42"
    assert "MyError()" not in repr(inner_error)

    outer_error = MyBatchError(errors=[inner_error])

    # the real message ("boom 42") now shows up in the outer error too...
    assert "boom 42" in str(outer_error)
    # ...and the useless default repr with empty args is gone
    assert "MyError()" not in str(outer_error)


def test_batch_delete_style_errors_keep_their_details():
    # FIXED BEHAVIOR: mirrors the real-world case in
    # simcore_service_webserver.projects.exceptions (ProjectDeleteError /
    # ProjectsBatchDeleteError), reproduced here with local stand-ins to keep this
    # package's tests dependency-free from the webserver service.
    class ProjectDeleteError(OsparcErrorMixin, Exception):
        msg_template = "Failed to complete deletion of '{project_uuid}': {details}"

    class ProjectsBatchDeleteError(OsparcErrorMixin, Exception):
        msg_template = "One or more projects could not be deleted in the batch: {errors}"

    project_uuid = "7a9aa11e-844f-11f1-ad6e-02420a0434d7"
    details = "some root cause explaining why deletion failed"

    inner_error = ProjectDeleteError(project_uuid=project_uuid, details=details)
    assert details in str(inner_error)

    batch_error = ProjectsBatchDeleteError(
        errors=[(project_uuid, inner_error)],
        deleted_project_ids=["other-project-id"],
    )

    # the actual failure reason is now visible in the batch error message...
    assert details in str(batch_error)
    # ...and the generic, indistinguishable default repr is gone
    assert "ProjectDeleteError()" not in str(batch_error)
    # successfully deleted projects remain (correctly) excluded from the message
    assert "other-project-id" not in str(batch_error)


def test_long_message_is_truncated():
    # Generic safety net: no single OsparcErrorMixin message should be allowed to grow
    # unbounded (e.g. many batched errors, or an accidentally embedded traceback/blob),
    # since that can blow past what log aggregators can handle in a single line.
    class MyError(OsparcErrorMixin, Exception):
        msg_template = "{value}"

    huge_value = "x" * 10_000
    error = MyError(value=huge_value)

    message = str(error)
    assert len(message) < len(huge_value)
    assert message.startswith("x" * 100)
    assert "truncated" in message

    # a short message is untouched
    short_error = MyError(value="short")
    assert str(short_error) == "short"

# pylint: disable=protected-access
# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable


from models_library.errors_classes import OsparcErrorMixin


def test_get_full_class_name():
    class A(OsparcErrorMixin):
        ...

    class B1(A):
        ...

    class B2(A):
        ...

    class C(B2):
        ...

    class B12(B1, ValueError):
        ...

    assert B1._get_full_class_name() == "A.B1"
    assert C._get_full_class_name() == "A.B2.C"
    assert A._get_full_class_name() == "A"

    # diamond inheritance (not usual but supported)
    assert B12._get_full_class_name() == "ValueError.A.B1.B12"


def test_error_codes_and_msg_template():
    class MyBaseError(OsparcErrorMixin, Exception):
        ...

    class MyValueError(MyBaseError, ValueError):
        msg_template = "Wrong value {value}"

    error = MyValueError(value=42)

    assert error.code == "ValueError.MyBaseError.MyValueError"
    assert f"{error}" == "Wrong value 42"

    class MyTypeError(MyBaseError, TypeError):
        code = "i_want_this"
        msg_template = "Wrong type {type}"

    error = MyTypeError(type="int")

    assert error.code == "i_want_this"
    assert f"{error}" == "Wrong type int"


def test_error_msg_template_override():
    class MyError(OsparcErrorMixin, Exception):
        msg_template = "Wrong value {value}"

    error_override_msg = MyError(msg_template="I want this message")
    assert str(error_override_msg) == "I want this message"

    error = MyError(value=42)
    assert hasattr(error, "value")
    assert str(error) == f"Wrong value {error.value}"


def test_error_with_constructor():
    class MyError(OsparcErrorMixin, ValueError):
        msg_template = "Wrong value {value}"

        # handy e.g. autocompletion
        def __init__(self, my_value: int = 42):
            self.value = my_value

    error = MyError(my_value=33)
    assert error.value == 33
    assert str(error) == "Wrong value 33"
    assert not hasattr(error, "my_value")

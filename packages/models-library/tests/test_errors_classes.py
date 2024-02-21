# pylint: disable=protected-access
# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable


from models_library.errors_classes import OsparcBaseError


def test_get_full_class_name():
    class A(OsparcBaseError):
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
    class MyBaseError(OsparcBaseError):
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

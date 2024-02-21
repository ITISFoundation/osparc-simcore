# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable


from models_library.errors_base import OsparcBaseError


def test_osparc_base_error_class():
    class A(OsparcBaseError):
        ...

    class B1(A):
        ...

    class B2(A):
        ...

    class C(B2):
        ...

    assert B1.get_full_class_name() == "OsparcBaseError.A.B1"
    assert C.get_full_class_name() == "OsparcBaseError.A.B2.C"
    assert A.get_full_class_name() == "OsparcBaseError.A"

    # TODO: check how pydantic adds code prefix/suffix upon creation

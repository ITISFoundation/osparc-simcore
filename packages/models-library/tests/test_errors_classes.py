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

    class B12(B1, B2):
        ...

    assert B1.get_full_class_name() == "OsparcBaseError.A.B1"
    assert C.get_full_class_name() == "OsparcBaseError.A.B2.C"
    assert A.get_full_class_name() == "OsparcBaseError.A"

    # diamond inheritance (not usual but supported)
    assert B12.get_full_class_name() == "OsparcBaseError.A.B2.B1.B12"

    # TODO: check how pydantic adds code prefix/suffix upon creation

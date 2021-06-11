# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable

from simcore_service_workflows.utils.function_factory import (
    _create_function_v1,
    _create_function_v2,
)

# TODO: keep annotations ???
# or at least metadata ???


def test_create_function_v1():
    from inspect import signature

    # TODO: metadata ( pulled from API? ) -> signature
    # TODO: create_function with same execution
    #
    # original function
    def original(a, b, *args, **kwargs):
        # TODO:
        # docker run
        # bind a,b,.... to CLI of run ?
        # capture outputs
        # returns serialized or pointers ...???
        #
        return a, b, args, kwargs

    sig = signature(original)
    print("original:", original)
    print("original signature:", sig)
    print("original ret:", original(1, 2, 4, borp="torp"))

    # cloned function
    def callback(*args, **kwargs):
        return args, kwargs

    cloned = _create_function_v1("clone", sig, callback)

    sig = signature(cloned)
    print("cloned:", cloned)
    print("cloned signature:", sig)
    print("cloned ret:", cloned(1, 2, 4, borp="torp"))


def test_create_function_v2():

    myfunc = _create_function_v2("myfunc", 3)

    print(repr(myfunc))
    print(myfunc.func_name)
    print(myfunc.func_code.co_argcount)

    myfunc(1, 2, 3, 4)
    # TypeError: myfunc() takes exactly 3 arguments (4 given)


if __name__ == "__main__":
    main()

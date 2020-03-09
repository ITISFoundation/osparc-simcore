from servicelib.decorators import safe_return


def test_safe_return_decorator():
    class MyException(Exception):
        pass

    @safe_return(if_fails_return=False, catch=(MyException,), logger=None)
    def raise_my_exception():
        raise MyException()

    assert not raise_my_exception()


def test_safe_return_mutables():
    some_mutable_return = ["some", "defaults"]

    @safe_return(if_fails_return=some_mutable_return)
    def return_mutable():
        raise RuntimeError("Runtime is default")

    assert return_mutable() == some_mutable_return  # contains the same
    assert not (return_mutable() is some_mutable_return)  # but is not the same

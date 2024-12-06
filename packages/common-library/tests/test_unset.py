from typing import Any

from common_library.unset import UnSet, as_dict_exclude_unset


def test_as_dict_exclude_unset():
    def f(
        par1: str | UnSet = UnSet.VALUE, par2: int | UnSet = UnSet.VALUE
    ) -> dict[str, Any]:
        return as_dict_exclude_unset(par1=par1, par2=par2)

    assert f() == {}
    assert f(par1="hi") == {"par1": "hi"}
    assert f(par2=4) == {"par2": 4}
    assert f(par1="hi", par2=4) == {"par1": "hi", "par2": 4}

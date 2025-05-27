from typing import Any

from common_library.exclude import Unset, as_dict_exclude_none, as_dict_exclude_unset


def test_as_dict_exclude_unset():
    def f(
        par1: str | Unset = Unset.VALUE, par2: int | Unset = Unset.VALUE
    ) -> dict[str, Any]:
        return as_dict_exclude_unset(par1=par1, par2=par2)

    assert f() == {}
    assert f(par1="hi") == {"par1": "hi"}
    assert f(par2=4) == {"par2": 4}
    assert f(par1="hi", par2=4) == {"par1": "hi", "par2": 4}

    # still expected behavior
    assert as_dict_exclude_unset(par1=None) == {"par1": None}


def test_as_dict_exclude_none():
    assert as_dict_exclude_none(par1=None) == {}

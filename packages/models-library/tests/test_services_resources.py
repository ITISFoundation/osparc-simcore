import pytest
from models_library.services_resources import ResourceValue


@pytest.mark.xfail()
def test_reservation_is_cap_by_limit_on_assigment_pydantic_2_bug():

    res = ResourceValue(limit=10, reservation=30)
    assert res.limit == 10
    assert res.reservation == 10

    # https://docs.pydantic.dev/latest/api/config/#pydantic.config.ConfigDict.validate_assignment
    # before-validators DO NOT work on Assignment!!!
    # SEE https://github.com/pydantic/pydantic/issues/7105
    res.reservation = 30
    assert res.reservation == 10

    # update here is not validated neither
    #
    # res.model_copy(update={"reservation": 30})
    #

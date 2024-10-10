import pytest
from common_library.pydantic_constrained import ValidatedRegisteredPortInt
from pydantic import ValidationError


def test_registered_port_int():
    for accepted_value in (1025, 1025.0, "1025", "1025.0"):
        ValidatedRegisteredPortInt(accepted_value)

    for invalid_value in (1, 1.0, "1", "1.0"):
        with pytest.raises(ValidationError):
            ValidatedRegisteredPortInt(invalid_value)

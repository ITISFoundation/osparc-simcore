import pytest
from common_library.masking import mask_phone_number


@pytest.mark.parametrize(
    "phone,expected",
    [
        ("+41791234567", "+41XXXXXXXX7"),
        ("+14155552671", "+14XXXXXXXX1"),
        ("+4179123", "+41XXXX3"),
    ],
)
def test_mask_phone_number_keeps_country_prefix_and_last_digit(phone: str, expected: str):
    assert mask_phone_number(phone) == expected


@pytest.mark.parametrize("phone", ["+41", "41791", ""])
def test_mask_phone_number_rejects_numbers_without_enough_digits(phone: str):
    with pytest.raises(AssertionError):
        mask_phone_number(phone)

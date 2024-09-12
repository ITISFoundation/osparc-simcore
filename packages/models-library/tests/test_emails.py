import pytest
from models_library.emails import LowerCaseEmailStr
from pydantic import BaseModel, ValidationError


class Profile(BaseModel):
    email: LowerCaseEmailStr


@pytest.mark.parametrize(
    "email_input", ["bla@gmail.com", "BlA@gMaIL.com", "BLA@GMAIL.COM"]
)
def test_lowercase_email(email_input: str):
    data = Profile(email=email_input)
    assert data.email == "bla@gmail.com"


@pytest.mark.parametrize("email_input", ["blagmail.com", "BlA@.com", "bLA@", ""])
def test_malformed_email(email_input: str):
    with pytest.raises(ValidationError):
        Profile(email=email_input)

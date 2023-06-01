import pytest
from models_library.emails import LowerCaseEmailStr
from pydantic import BaseModel


@pytest.mark.parametrize(
    "email_input", ["bla@gmail.com", "BlA@gMaIL.com", "BLA@GMAIL.COM"]
)
def test_lowercase_email(email_input: str):
    class Profile(BaseModel):
        email: LowerCaseEmailStr

    data = Profile(email=email_input)
    assert data.email == "bla@gmail.com"

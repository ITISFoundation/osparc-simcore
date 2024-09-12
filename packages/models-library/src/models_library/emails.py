from typing import Annotated

from pydantic import AfterValidator, EmailStr

LowerCaseEmailStr = Annotated[str, EmailStr, AfterValidator(str.lower)]

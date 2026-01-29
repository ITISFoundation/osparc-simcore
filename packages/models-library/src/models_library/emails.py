from typing import Annotated

from pydantic import AfterValidator, EmailStr

type LowerCaseEmailStr = Annotated[str, EmailStr, AfterValidator(str.lower)]

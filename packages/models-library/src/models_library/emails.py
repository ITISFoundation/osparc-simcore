from typing import Annotated, TypeAlias

from pydantic import AfterValidator, EmailStr

LowerCaseEmailStr: TypeAlias = Annotated[str, EmailStr, AfterValidator(str.lower)]

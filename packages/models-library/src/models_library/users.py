from typing import TypeAlias

from pydantic import ConstrainedStr, PositiveInt

UserID: TypeAlias = PositiveInt
GroupID: TypeAlias = PositiveInt


class FirstNameStr(ConstrainedStr):
    strip_whitespace = True
    min_length = 1
    max_length = 255


LastNameStr: TypeAlias = FirstNameStr

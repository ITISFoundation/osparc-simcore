from typing import TypeAlias

from pydantic import ConstrainedStr, PositiveInt

UserID: TypeAlias = PositiveInt
GroupID: TypeAlias = PositiveInt


class FirstNameStr(ConstrainedStr):
    strip_whitespace = True
    max_length = 255


class LastNameStr(FirstNameStr):
    ...

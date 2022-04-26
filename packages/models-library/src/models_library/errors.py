from typing import Any, Dict, Tuple, TypedDict, Union

Loc = Tuple[Union[int, str], ...]


class _ErrorDictRequired(TypedDict):
    """
    loc: identifies path in nested model e.g. ("parent", "child", "field", 0)
    type: set to code defined pydantic.errors raised upon validation
        (i.e. inside @validator decorated functions)
    """

    loc: Loc
    msg: str
    type: str

    # SEE tests_errors for more details


class ErrorDict(_ErrorDictRequired, total=False):
    """Structured dataset returned by pydantic's ValidationError.errors() -> List[ErrorDict]"""

    ctx: Dict[str, Any]


# WARNING: 'from pydantic.error_wrappers import ErrorDict' only works in development

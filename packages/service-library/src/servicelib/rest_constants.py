# SEE https://pydantic-docs.helpmanual.io/usage/exporting_models/#modeldict

from typing import Final, TypedDict


class PydanticExportParametersDict(TypedDict):
    by_alias: bool
    exclude_unset: bool
    exclude_defaults: bool
    exclude_none: bool


RESPONSE_MODEL_POLICY = PydanticExportParametersDict(
    by_alias=True,
    exclude_unset=True,
    exclude_defaults=False,
    exclude_none=False,
)

# Headers keys
X_PRODUCT_NAME_HEADER: Final[str] = "X-Simcore-Products-Name"

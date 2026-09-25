from typing import TypeAlias

# NOTE: intentionally kept as a `TypeAlias` assignment (not a PEP 695 `type` statement):
# it is consumed at runtime inside FastAPI annotations, e.g.
# `Annotated[ProductName, Depends(get_product_name)]`, where the alias must stay a
# plain runtime-resolvable typing object.
ProductName: TypeAlias = str
StripePriceID: TypeAlias = str
StripeTaxRateID: TypeAlias = str

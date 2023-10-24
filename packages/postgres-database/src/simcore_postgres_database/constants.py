from decimal import Decimal
from typing import Final

# NOTE: this is sync with DECIMAL_PLACES@ packages/models-library/src/models_library/basic_types.py using test_postgres_and_models_library_same_decimal_places_constant
DECIMAL_PLACES: Final = 2

# NOTE: Constant used in the exp argument of quantize to convert decimals as: Decimal().quantize(QUANTIZE_EXP_ARG)
# See https://docs.python.org/3/library/decimal.html#decimal.Decimal.quantize
QUANTIZE_EXP_ARG: Final = Decimal(f"1e-{DECIMAL_PLACES}")

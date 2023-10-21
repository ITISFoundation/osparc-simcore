from decimal import Decimal
from typing import Final

# NOTE: this is sync with DECIMAL_PLACES@ packages/models-library/src/models_library/basic_types.py using test_postgres_and_models_library_same_decimal_places_constant
DECIMAL_PLACES: Final = 2
QUANTIZE_EXP_ARG: Final = Decimal(f"1e-{DECIMAL_PLACES}")

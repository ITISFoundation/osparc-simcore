from ...services import (
    ServiceInput,
    ServiceMetaDataPublished,
    ServiceOutput,
    ServiceType,
)
from ...services_constants import LATEST_INTEGRATION_VERSION
from .._key_labels import FUNCTION_SERVICE_KEY_PREFIX
from .._utils import OM, PC, FunctionServices, create_fake_thumbnail_url

# SEE https://github.com/hgrecco/pint/blob/master/pint/default_en.txt
#
# NOTE: this service is also used as fixture in test_catalog_utils.py::test_can_connect_with_units
#       and assumes for convenience that matching 'Titles' correspond to compatible units.
#       If this assumption cannot be guaranteed anymore the test must be updated.
#

META = ServiceMetaDataPublished.model_validate(
    {
        "integration-version": LATEST_INTEGRATION_VERSION,
        "key": f"{FUNCTION_SERVICE_KEY_PREFIX}/data-iterator/demo-units",
        "version": "0.2.0",
        # CHANGELOG
        # - 0.2.0: reverted order of first 5 outputs
        "type": ServiceType.BACKEND,
        "name": "Demo Units",
        "description": "This service is for demo purposes."
        "It takes base units as inputs and transform them in the outputs.",
        "authors": [PC, OM],
        "contact": PC.email,
        "thumbnail": create_fake_thumbnail_url("demo-units"),
        "inputs": {
            "length": ServiceInput.from_json_schema(
                {
                    "title": "Distance",
                    "minimum": 0,
                    "maximum": 10,
                    "x_unit": "meter",
                    "type": "number",
                }
            ),
            "time": ServiceInput.from_json_schema(
                {
                    "title": "Time",
                    "description": "Positive time",
                    "minimum": 0,
                    "x_unit": "micro-second",
                    "type": "number",
                }
            ),
            "current": ServiceInput.from_json_schema(
                {
                    "title": "Current",
                    "x_unit": "ampere",
                    "type": "number",
                }
            ),
            "luminosity": ServiceInput.from_json_schema(
                {
                    "title": "Luminosity",
                    "x_unit": "candela",
                    "type": "number",
                }
            ),
            "mass": ServiceInput.from_json_schema(
                {
                    "title": "Mass",
                    "description": "Positive mass",
                    "minimum": 0,
                    "x_unit": "micro-gram",
                    "type": "number",
                }
            ),
            "substance": ServiceInput.from_json_schema(
                {
                    "title": "Substance",
                    "minimum": 0,
                    "x_unit": "milli-mole",
                    "type": "number",
                }
            ),
            "temperature": ServiceInput.from_json_schema(
                {
                    "title": "Temperature",
                    "minimum": 0,
                    "x_unit": "kelvin",
                    "type": "number",
                }
            ),
            "angle": ServiceInput.from_json_schema(
                {
                    "title": "Angle",
                    "x_unit": "degree",
                    "type": "number",
                }
            ),
            "velocity": ServiceInput.from_json_schema(
                {
                    "title": "Velo-city",
                    "x_unit": "meter_per_second",
                    "type": "number",
                }
            ),
            "entropy": ServiceInput.from_json_schema(
                {
                    "title": "Entropy",
                    "x_unit": "m**2 kg/s**2/K",
                    "type": "number",
                }
            ),
            "radiation": ServiceInput.from_json_schema(
                {
                    "title": "Radiation",
                    "x_unit": "rutherford",
                    "type": "number",
                }
            ),
        },
        "outputs": {
            "mass": ServiceOutput.from_json_schema(
                {
                    "title": "Mass",
                    "minimum": 0,
                    "x_unit": "kilo-gram",
                    "type": "number",
                }
            ),
            "luminosity": ServiceOutput.from_json_schema(
                {
                    "title": "Luminosity",
                    "x_unit": "candela",
                    "type": "number",
                }
            ),
            "current": ServiceOutput.from_json_schema(
                {
                    "title": "Current",
                    "x_unit": "milli-ampere",
                    "type": "number",
                }
            ),
            "time": ServiceOutput.from_json_schema(
                {
                    "title": "Time",
                    "minimum": 0,
                    "x_unit": "minute",
                    "type": "number",
                }
            ),
            "length": ServiceOutput.from_json_schema(
                {
                    "title": "Distance",
                    "description": "Distance value converted",
                    "x_unit": "milli-meter",
                    "type": "number",
                }
            ),
            "substance": ServiceOutput.from_json_schema(
                {
                    "title": "Substance",
                    "minimum": 0,
                    "x_unit": "mole",
                    "type": "number",
                }
            ),
            "temperature": ServiceOutput.from_json_schema(
                {
                    "title": "Temperature",
                    "minimum": 0,
                    "x_unit": "degree_Celsius",
                    "type": "number",
                }
            ),
            "angle": ServiceOutput.from_json_schema(
                {
                    "title": "Angle",
                    "x_unit": "radian",
                    "type": "number",
                }
            ),
            "velocity": ServiceOutput.from_json_schema(
                {
                    "title": "Velo-city",
                    "x_unit": "kilometer_per_hour",
                    "type": "number",
                }
            ),
            "radiation": ServiceOutput.from_json_schema(
                {
                    "title": "Radiation",
                    "x_unit": "curie",
                    "type": "number",
                }
            ),
        },
    },
)


services = FunctionServices()
services.add(
    meta=META,
    is_under_development=True,
)

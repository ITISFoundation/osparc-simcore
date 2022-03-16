from ..services import LATEST_INTEGRATION_VERSION, ServiceDockerData, ServiceType
from ._utils import OM, PC, create_fake_thumbnail_url, register
from .constants import FUNCTION_SERVICE_KEY_PREFIX


def build_input(schema):
    return {
        "label": schema["title"],
        "description": schema["description"],
        "type": "ref_contentSchema",
        "contentSchema": schema,
    }


# SEE https://github.com/hgrecco/pint/blob/master/pint/default_en.txt
META = ServiceDockerData.parse_obj(
    {
        "integration-version": LATEST_INTEGRATION_VERSION,
        "key": f"{FUNCTION_SERVICE_KEY_PREFIX}/data-iterator/demo-units",
        "version": "0.1.0",
        "type": ServiceType.BACKEND,
        "name": "Demo Units",
        "description": "Demo that takes base units as inputs and transform them in the outputs",
        "authors": [PC, OM],
        "contact": PC.email,
        "thumbnail": create_fake_thumbnail_url("demo-units"),
        "inputs": {
            "length": build_input(
                {
                    "title": "Distance",
                    "description": "Distance base unit",
                    "minimum": 0,
                    "maximum": 10,
                    "x_unit": "meter",
                    "type": "number",
                }
            ),
            "time": build_input(
                {
                    "title": "Time",
                    "description": "Positive time base unit",
                    "minimum": 0,
                    "x_unit": "micro-second",
                    "type": "number",
                }
            ),
            "current": build_input(
                {
                    "title": "Current",
                    "description": "Current base unit",
                    "x_unit": "ampere",
                    "type": "number",
                }
            ),
            "luminosity": build_input(
                {
                    "title": "Luminosity",
                    "description": "Luminosity base unit",
                    "x_unit": "candela",
                    "type": "number",
                }
            ),
            "mass": build_input(
                {
                    "title": "Mass",
                    "description": "Positive mass base unit",
                    "minimum": 0,
                    "x_unit": "micro-gram",
                    "type": "number",
                }
            ),
            "substance": build_input(
                {
                    "title": "Substance",
                    "description": "Substance base unit",
                    "minimum": 0,
                    "x_unit": "milli-mole",
                    "type": "number",
                }
            ),
            "temperature": build_input(
                {
                    "title": "Temperature",
                    "description": "Temperature in Kelvin",
                    "minimum": 0,
                    "x_unit": "kelvin",
                    "type": "number",
                }
            ),
            "angle": build_input(
                {
                    "title": "Angle",
                    "description": "Angle in degrees",
                    "x_unit": "degree",
                    "type": "number",
                }
            ),
        },
        "outputs": {
            "length": build_input(
                {
                    "title": "Distance",
                    "description": "Distance converted to millimeter",
                    "x_unit": "milli-meter",
                    "type": "number",
                }
            ),
            "time": build_input(
                {
                    "title": "Time",
                    "description": "Time in minutes",
                    "minimum": 0,
                    "x_unit": "minute",
                    "type": "number",
                }
            ),
            "current": build_input(
                {
                    "title": "Current",
                    "description": "Current in milliAmpere",
                    "x_unit": "milli-ampere",
                    "type": "number",
                }
            ),
            "luminosity": build_input(
                {
                    "title": "Luminosity",
                    "description": "Luminosity with the same units",
                    "x_unit": "candela",
                    "type": "number",
                }
            ),
            "mass": build_input(
                {
                    "title": "Mass",
                    "description": "Mass in kg",
                    "minimum": 0,
                    "x_unit": "kilo-gram",
                    "type": "number",
                }
            ),
            "substance": build_input(
                {
                    "title": "Substance",
                    "description": "Substance with no change in units",
                    "minimum": 0,
                    "x_unit": "mole",
                    "type": "number",
                }
            ),
            "temperature": build_input(
                {
                    "title": "Temperature",
                    "description": "Temperature converted to celcius",
                    "minimum": 0,
                    "x_unit": "degree_Celsius",
                    "type": "number",
                }
            ),
            "angle": build_input(
                {
                    "title": "Angle",
                    "description": "Angle converted to radians",
                    "x_unit": "radian",
                    "type": "number",
                }
            ),
        },
    },
)


# TODO: register ONLY when dev-feature is enabled
REGISTRY = register(META)

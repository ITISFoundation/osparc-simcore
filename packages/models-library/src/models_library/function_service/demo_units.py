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
                    "x_unit": "m",
                    "type": "number",
                }
            ),
            "time": build_input(
                {
                    "title": "Time",
                    "description": "Positive time base unit",
                    "minimum": 0,
                    "x_unit": "s",
                    "type": "number",
                }
            ),
            "current": build_input(
                {
                    "title": "Current",
                    "description": "Current base unit",
                    "x_unit": "A",
                    "type": "number",
                }
            ),
            "luminosity": build_input(
                {
                    "title": "Luminosity",
                    "description": "Luminosity base unit",
                    "x_unit": "cd",
                    "type": "number",
                }
            ),
            "mass": build_input(
                {
                    "title": "Mass",
                    "description": "Positive mass base unit",
                    "minimum": 0,
                    "x_unit": "g",
                    "type": "number",
                }
            ),
            "substance": build_input(
                {
                    "title": "Substance",
                    "description": "Substance base unit",
                    "minimum": 0,
                    "x_unit": "mol",
                    "type": "number",
                }
            ),
            "temperature": build_input(
                {
                    "title": "Temperature",
                    "description": "Temperature in Kelvin",
                    "minimum": 0,
                    "x_unit": "K",
                    "type": "number",
                }
            ),
            "angle": build_input(
                {
                    "title": "Angle",
                    "description": "Angle in degrees",
                    "x_unit": "deg",
                    "type": "number",
                }
            ),
        },
        "outputs": {
            "length": build_input(
                {
                    "title": "Distance",
                    "description": "Distance converted to millimeter",
                    "x_unit": "mm",
                    "type": "number",
                }
            ),
            "time": build_input(
                {
                    "title": "Time",
                    "description": "Time in minutes",
                    "minimum": 0,
                    "x_unit": "min",
                    "type": "number",
                }
            ),
            "current": build_input(
                {
                    "title": "Current",
                    "description": "Current in milliAmpere",
                    "x_unit": "mA",
                    "type": "number",
                }
            ),
            "luminosity": build_input(
                {
                    "title": "Luminosity",
                    "description": "Luminosity with the same units",
                    "x_unit": "cd",
                    "type": "number",
                }
            ),
            "mass": build_input(
                {
                    "title": "Mass",
                    "description": "Mass in kg",
                    "minimum": 0,
                    "x_unit": "kg",
                    "type": "number",
                }
            ),
            "substance": build_input(
                {
                    "title": "Substance",
                    "description": "Substance with no change in units",
                    "minimum": 0,
                    "x_unit": "mol",
                    "type": "number",
                }
            ),
            "temperature": build_input(
                {
                    "title": "Temperature",
                    "description": "Temperature converted to celcius",
                    "minimum": 0,
                    "x_unit": "°C",
                    "type": "number",
                }
            ),
            "angle": build_input(
                {
                    "title": "Angle",
                    "description": "Angle converted to radians",
                    "x_unit": "rad",
                    "type": "number",
                }
            ),
        },
    },
)


# TODO: register ONLY when dev-feature is enabled
REGISTRY = register(META)

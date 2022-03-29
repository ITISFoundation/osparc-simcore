from models_library.services import (
    LATEST_INTEGRATION_VERSION,
    ServiceDockerData,
    ServiceType,
)

from ._utils import OM, PC, create_fake_thumbnail_url, register
from .constants import FUNCTION_SERVICE_KEY_PREFIX


def build_input(schema):
    description = schema.pop("description", schema["title"])

    return {
        "label": schema["title"],
        "description": description,
        "type": "ref_contentSchema",
        "contentSchema": schema,
    }


# SEE https://github.com/hgrecco/pint/blob/master/pint/default_en.txt

META = ServiceDockerData.parse_obj(
    {
        "integration-version": LATEST_INTEGRATION_VERSION,
        "key": f"{FUNCTION_SERVICE_KEY_PREFIX}/data-iterator/demo-units",
        "version": "0.2.0",
        # CHANGELOG
        # - 0.2.0: reverted order of first 5 outputs
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
                    "minimum": 0,
                    "maximum": 10,
                    "x_unit": "meter",
                    "type": "number",
                }
            ),
            "time": build_input(
                {
                    "title": "Time",
                    "description": "Positive time",
                    "minimum": 0,
                    "x_unit": "micro-second",
                    "type": "number",
                }
            ),
            "current": build_input(
                {
                    "title": "Current",
                    "x_unit": "ampere",
                    "type": "number",
                }
            ),
            "luminosity": build_input(
                {
                    "title": "Luminosity",
                    "x_unit": "candela",
                    "type": "number",
                }
            ),
            "mass": build_input(
                {
                    "title": "Mass",
                    "description": "Positive mass",
                    "minimum": 0,
                    "x_unit": "micro-gram",
                    "type": "number",
                }
            ),
            "substance": build_input(
                {
                    "title": "Substance",
                    "minimum": 0,
                    "x_unit": "milli-mole",
                    "type": "number",
                }
            ),
            "temperature": build_input(
                {
                    "title": "Temperature",
                    "minimum": 0,
                    "x_unit": "kelvin",
                    "type": "number",
                }
            ),
            "angle": build_input(
                {
                    "title": "Angle",
                    "x_unit": "degree",
                    "type": "number",
                }
            ),
            "velocity": build_input(
                {
                    "title": "Velo-city",
                    "x_unit": "meter_per_second",
                    "type": "number",
                }
            ),
            "entropy": build_input(
                {
                    "title": "Entropy",
                    "x_unit": "m**2 kg/s**2/K",
                    "type": "number",
                }
            ),
            "radiation": build_input(
                {
                    "title": "Radiation",
                    "x_unit": "roentgen",
                    "type": "number",
                }
            ),
        },
        "outputs": {
            "mass": build_input(
                {
                    "title": "Mass",
                    "minimum": 0,
                    "x_unit": "kilo-gram",
                    "type": "number",
                }
            ),
            "luminosity": build_input(
                {
                    "title": "Luminosity",
                    "x_unit": "candela",
                    "type": "number",
                }
            ),
            "current": build_input(
                {
                    "title": "Current",
                    "x_unit": "milli-ampere",
                    "type": "number",
                }
            ),
            "time": build_input(
                {
                    "title": "Time",
                    "minimum": 0,
                    "x_unit": "minute",
                    "type": "number",
                }
            ),
            "length": build_input(
                {
                    "title": "Distance",
                    "description": "Distance value converted",
                    "x_unit": "milli-meter",
                    "type": "number",
                }
            ),
            "substance": build_input(
                {
                    "title": "Substance",
                    "minimum": 0,
                    "x_unit": "mole",
                    "type": "number",
                }
            ),
            "temperature": build_input(
                {
                    "title": "Temperature",
                    "minimum": 0,
                    "x_unit": "degree_Celsius",
                    "type": "number",
                }
            ),
            "angle": build_input(
                {
                    "title": "Angle",
                    "x_unit": "radian",
                    "type": "number",
                }
            ),
            "velocity": build_input(
                {
                    "title": "Velo-city",
                    "x_unit": "kilometer_per_hour",
                    "type": "number",
                }
            ),
            "radiation": build_input(
                {
                    "title": "Radiati0n",  # it's not a typo
                    "x_unit": "curie",
                    "type": "number",
                }
            ),
        },
    },
)


# TODO: register ONLY when dev-feature is enabled
REGISTRY = register(META)

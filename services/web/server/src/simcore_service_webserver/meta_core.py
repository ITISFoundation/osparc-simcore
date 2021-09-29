import collections.abc
import inspect
from typing import Any, Callable, Optional, Type, get_origin, get_type_hints

from models_library.frontend_services_catalog import FRONTEND_SERVICE_KEY_PREFIX, OM
from models_library.services import ServiceDockerData
from pydantic.fields import Field
from pydantic.main import BaseModel

PROPTYPE_2_PYTYPE = {"number": float, "boolean": bool, "integer": int, "string": str}
PYTYPE_2_PROPTYPE = {v: k for k, v in PROPTYPE_2_PYTYPE.items()}


class Info(BaseModel):
    key: str
    version: str
    name: str
    description: Optional[str] = None

    @property
    def unique_id(self):
        """hashable unique identifier"""
        return (self.key, self.version)


class BaseFuncDef:
    info: Info
    Inputs: Type[BaseModel]
    Outputs: Type[BaseModel]
    _compute: Callable
    _compute_meta: Optional[Callable] = None

    @classmethod
    def run(cls, **kwargs):
        assert cls.Inputs
        assert cls._compute
        assert cls.Outputs

        _inputs = cls.Inputs.parse_obj(kwargs)
        return cls.run_with_model(_inputs)

    @classmethod
    def collect_outputs(cls, returned: Any):
        if not isinstance(returned, tuple):
            returned = (returned,)
        obj = dict(zip(cls.Outputs.__fields__.keys(), returned))
        return cls.Outputs.parse_obj(obj)

    @classmethod
    def run_with_model(cls, inputs: BaseModel):
        _returned = cls._compute(**inputs.dict())
        outputs = cls.collect_outputs(_returned)
        return inputs, outputs

    @classmethod
    def is_iterable(cls) -> bool:
        return_hint = get_type_hints(cls._compute).get("return")
        if return_cls := get_origin(return_hint):
            return issubclass(return_cls, collections.abc.Iterable)
        return False

    @classmethod
    def to_dockerdata(cls) -> ServiceDockerData:
        inputs = {}
        for name, model_field in cls.Inputs.__fields__.items():
            inputs[name] = {
                "label": name,
                "description": model_field.field_info.description or "",
                "type": PYTYPE_2_PROPTYPE[model_field.type_],
                "defaultValue": model_field.default,
            }

        outputs = {}
        for name, model_field in cls.Outputs.__fields__.items():
            outputs[name] = {
                "label": name,
                "description": model_field.field_info.description or "",
                "type": PYTYPE_2_PROPTYPE[model_field.type_],
            }

        data = {
            "integration-version": "1.0.0",
            "type": "computational",
            "authors": [
                OM,
            ],
            "contact": OM.email,
            **cls.info.dict(),
            **{"inputs": inputs, "outputs": outputs},
        }
        return ServiceDockerData.parse_obj(data)


# Functional Services -------
#
# A functional service requires two classes, namely a *Def and a *Data class
#  - The *Def class defines the info, inputs/output schema and the implementation function
#  - Having models for i/o allows defining both single and composed constraints on the fields (e.g. x>1 and y<x)
#     - single constraints can be reflected in the json-schema (i.e. descriptive constraints)
#     - composed constraints are programatic only (i.e. programatic constraints)
#
class SumDiffDef(BaseFuncDef):
    info = Info(
        name="sum-diff",
        key=f"{FRONTEND_SERVICE_KEY_PREFIX}/def/sum-diff",
        version="1.0.0",
        description="Sum and different of two numbers",
    )

    # NOTE: Inputs/outputs should be easily parsed from signatures
    class Inputs(BaseModel):
        x: float
        y: float = 3

    class Outputs(BaseModel):
        sum: float = Field(..., description="Sum of all inputs")
        diff: float = Field(..., description="Difference between inputs")

    # NOTE: ? language that operates on fields ... (e.g. to propagate inputs to output units)
    @classmethod
    def _compute_meta(cls, x, y):
        # some meta of x and y is known, might be able to determine Outputs ?
        assert cls.Outputs  # nosec
        # cls.Outputs =
        raise NotImplementedError

    @staticmethod
    def _compute(x, y):
        return x + y, x - y


class SumDiffData(BaseModel):
    info: Info = SumDiffDef.info
    inputs: SumDiffDef.Inputs
    outputs: Optional[SumDiffDef.Outputs] = None

    @classmethod
    def from_io(cls, inputs, outputs) -> "SumDiffData":
        return cls(inputs=inputs, outputs=outputs)


##############################################


def extract_ios(fun: Callable):
    # TODO:
    sig = inspect.signature(fun)

    # param -> field
    fields = []
    for param in sig.parameters.values():
        if param.kind == param.POSITIONAL_ONLY:
            raise ValueError(f"{param.name}: positional only not allowed")

        if param.annotation == param.empty:
            raise ValueError(f"{param.name} was not annotated")

        pydantic_type = param.annotation

        field_args = {}
        if param.default != param.empty:
            field_args["default"] = param.default

    # if not issubclass(sig.return_annotation, tuple):


# /projects/{project_uuid}/workbench:start

# pre-process
#   - any meta nodes?
#      - no
#           - then forward to director_v2_handlers.start_pipeline TODO: adapt so it is callable
#      - yes
#           - create replicas and commit
#           - convert every commit in a project
#           - launch these projects -> start_pipeline
#

# /projects/{project_uuid}/workbench:stop

# meta project (uuid) -> concrete projects  (uuid,tagid)


# these services have a backend implementation

# convert ServiceDockerData into functions??
#

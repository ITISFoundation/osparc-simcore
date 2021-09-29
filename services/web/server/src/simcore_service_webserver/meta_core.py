import inspect
from typing import Any, Callable, Optional, Type

from models_library.frontend_services_catalog import FRONTEND_SERVICE_KEY_PREFIX
from pydantic.fields import Field
from pydantic.main import BaseModel

PROPTYPE_2_PYTYPE = {"number": float, "boolean": bool, "integer": int, "string": str}
PYTYPE_2_PROPTYPE = {v: k for k, v in PROPTYPE_2_PYTYPE.items()}


class Info(BaseModel):
    key: str
    version: str
    name: str
    description: Optional[str] = None


class FunctionalMixin:
    Inputs: Type[BaseModel]
    Outputs: Type[BaseModel]
    _impl: Callable

    @classmethod
    def run(cls, **kwargs):
        assert cls.Inputs
        assert cls._impl
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
        _returned = cls._impl(**inputs.dict())
        outputs = cls.collect_outputs(_returned)
        return inputs, outputs


# Concrete Functional Services -------
class SumDiffDef(FunctionalMixin):
    info = Info(
        name="sum-diff",
        key=f"{FRONTEND_SERVICE_KEY_PREFIX}/def/sum-diff",
        version="1.0.0",
        description="Sum and different of two numbers",
    )

    # NOTE: INputs/outputs should be easily parsed from signatures
    class Inputs(BaseModel):
        x: float
        y: float = 3

    class Outputs(BaseModel):
        sum: float = Field(..., description="Sum of all inputs")
        diff: float = Field(..., description="Difference between inputs")

    @staticmethod
    def _impl(x, y):
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

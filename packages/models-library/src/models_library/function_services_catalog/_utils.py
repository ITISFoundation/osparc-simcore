import inspect
import logging
from collections.abc import Callable, Iterator
from dataclasses import dataclass
from typing import Any, get_args, get_origin
from urllib.parse import quote

from ..services import Author, ServiceKey, ServiceMetaDataPublished, ServiceVersion
from ..services_io import ServiceInput, ServiceOutput
from ._settings import AUTHORS, FunctionServiceSettings

_logger = logging.getLogger(__name__)


_DEFAULT = {
    "name": "Unknown",
    "email": "unknown@osparc.io",
    "affiliation": "unknown",
}
EN = Author.model_validate(AUTHORS.get("EN", _DEFAULT))
OM = Author.model_validate(AUTHORS.get("OM", _DEFAULT))
PC = Author.model_validate(AUTHORS.get("PC", _DEFAULT))
WVG = Author.model_validate(AUTHORS.get("WVG", _DEFAULT))


def create_fake_thumbnail_url(label: str) -> str:
    return f"https://fakeimg.pl/100x100/ff0000%2C128/000%2C255/?text={quote(label)}"


class ServiceNotFoundError(KeyError):
    pass


@dataclass
class _Record:
    meta: ServiceMetaDataPublished
    implementation: Callable | None = None
    is_under_development: bool = False


_TYPE_MAPPING = {
    "number": float,
    "integer": int,
    "boolean": bool,
    "string": str,
    "data:*/*": str,
    "ref_contentSchema": type[Any],
}


def _service_type_to_python_type(property_type: str) -> type[Any]:
    """Convert service property type to Python type"""
    # Fast lookup for exact matches
    if mapped_type := _TYPE_MAPPING.get(property_type):
        return mapped_type

    # Handle data: prefix patterns
    if property_type.startswith("data:"):
        return str

    # Default to Any for unknown types
    return type[Any]


def validate_callable_signature(
    implementation: Callable | None,
    service_inputs: dict[str, ServiceInput] | None,
    service_outputs: dict[str, ServiceOutput] | None,
) -> None:
    """
    Validates that the callable signature matches the service inputs and outputs.

    Args:
        implementation: The callable to validate
        service_inputs: Dictionary of service input specifications
        service_outputs: Dictionary of service output specifications

    Raises:
        ValueError: If signature doesn't match the expected inputs/outputs
        TypeError: If types are incompatible
    """
    if implementation is None:
        return

    sig = inspect.signature(implementation)
    service_inputs = service_inputs or {}
    service_outputs = service_outputs or {}

    # Validate input parameters
    sig_params = list(sig.parameters.values())
    expected_input_count = len(service_inputs)
    actual_input_count = len(
        [
            p
            for p in sig_params
            if p.kind in (p.POSITIONAL_ONLY, p.POSITIONAL_OR_KEYWORD)
        ]
    )

    if actual_input_count != expected_input_count:
        msg = f"Function has {actual_input_count} parameters but service expects {expected_input_count} inputs"
        raise ValueError(msg)

    # Check parameter types if type hints are available
    for i, (input_key, input_spec) in enumerate(service_inputs.items()):
        assert input_key  # nosec
        if i < len(sig_params):
            param = sig_params[i]
            expected_type = _service_type_to_python_type(input_spec.property_type)

            if param.annotation != inspect.Parameter.empty and expected_type != Any:
                param_type = param.annotation
                # Handle Union types and optional parameters
                if get_origin(param_type) is not None:
                    param_types = get_args(param_type)
                    if expected_type not in param_types:
                        _logger.warning(
                            "Parameter '%s' type hint %s doesn't match expected service input type %s",
                            param.name,
                            param_type,
                            expected_type,
                        )
                elif param_type != expected_type:
                    _logger.warning(
                        "Parameter '%s' type hint %s doesn't match expected service input type %s",
                        param.name,
                        param_type,
                        expected_type,
                    )

    # Validate return type
    if service_outputs:
        return_annotation = sig.return_annotation
        if return_annotation != inspect.Signature.empty:
            output_count = len(service_outputs)

            # If single output, return type should match directly
            if output_count == 1:
                output_spec = next(iter(service_outputs.values()))
                expected_return_type = _service_type_to_python_type(
                    output_spec.property_type
                )

                if return_annotation not in {Any, expected_return_type}:
                    # Check if it's a Union type containing the expected type
                    if get_origin(return_annotation) is not None:
                        return_types = get_args(return_annotation)
                        if expected_return_type not in return_types:
                            _logger.warning(
                                "Return type %s doesn't match expected service output type %s",
                                return_annotation,
                                expected_return_type,
                            )
                    else:
                        _logger.warning(
                            "Return type %s doesn't match expected service output type %s",
                            return_annotation,
                            expected_return_type,
                        )

            # If multiple outputs, expect tuple or dict return type
            elif output_count > 1:
                if get_origin(return_annotation) not in (tuple, dict):
                    _logger.warning(
                        "Multiple outputs expected but return type %s is not tuple or dict",
                        return_annotation,
                    )


class FunctionServices:
    """Used to register a collection of function services"""

    def __init__(self, settings: FunctionServiceSettings | None = None):
        self._functions: dict[tuple[ServiceKey, ServiceVersion], _Record] = {}
        self.settings = settings

    def add(
        self,
        meta: ServiceMetaDataPublished,
        implementation: Callable | None = None,
        *,
        is_under_development: bool = False,
    ):
        """
        raises ValueError
        """
        if not isinstance(meta, ServiceMetaDataPublished):
            msg = f"Expected ServiceDockerData, got {type(meta)}"
            raise TypeError(msg)

        # ensure unique
        if (meta.key, meta.version) in self._functions:
            msg = f"{meta.key, meta.version} is already registered"
            raise ValueError(msg)

        # Validate callable signature matches metadata
        validate_callable_signature(implementation, meta.inputs, meta.outputs)

        # register
        self._functions[(meta.key, meta.version)] = _Record(
            meta=meta,
            implementation=implementation,
            is_under_development=is_under_development,
        )

    def extend(self, other: "FunctionServices"):
        # pylint: disable=protected-access
        for f in other._functions.values():  # noqa: SLF001
            self.add(
                f.meta, f.implementation, is_under_development=f.is_under_development
            )

    def _skip_dev(self):
        skip = True
        if self.settings:
            skip = not self.settings.is_dev_feature_enabled()
        return skip

    def _items(
        self,
    ) -> Iterator[tuple[tuple[ServiceKey, ServiceVersion], _Record]]:
        skip_dev = self._skip_dev()
        for key, value in self._functions.items():
            if value.is_under_development and skip_dev:
                continue
            yield key, value

    def iter_metadata(self) -> Iterator[ServiceMetaDataPublished]:
        """WARNING: this function might skip services marked as 'under development'"""
        for _, f in self._items():
            yield f.meta

    def iter_services_key_version(
        self,
    ) -> Iterator[tuple[ServiceKey, ServiceVersion]]:
        """WARNING: this function might skip services makred as 'under development'"""
        for kv, f in self._items():
            assert kv == (f.meta.key, f.meta.version)  # nosec
            yield kv

    def get_implementation(
        self, service_key: ServiceKey, service_version: ServiceVersion
    ) -> Callable | None:
        """raises ServiceNotFound"""
        try:
            func = self._functions[(service_key, service_version)]
        except KeyError as err:
            msg = f"{service_key}:{service_version} not found in registry"
            raise ServiceNotFoundError(msg) from err
        return func.implementation

    def get_metadata(
        self, service_key: ServiceKey, service_version: ServiceVersion
    ) -> ServiceMetaDataPublished:
        """raises ServiceNotFound"""
        try:
            func = self._functions[(service_key, service_version)]
        except KeyError as err:
            msg = f"{service_key}:{service_version} not found in registry"
            raise ServiceNotFoundError(msg) from err
        return func.meta

    def __len__(self):
        return len(self._functions)

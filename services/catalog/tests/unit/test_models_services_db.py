# pytest unit tests for the database models in `simcore_service_catalog.models.services_db`

from datetime import UTC, datetime, timedelta, timezone

import pytest
from models_library.services_types import ServiceKey, ServiceVersion
from simcore_service_catalog.models.services_db import (
    ServiceMetaDataDBCreate,
    ServiceMetaDataDBPatch,
)

_KEY: ServiceKey = "simcore/services/comp/isolve"
_VERSION: ServiceVersion = "1.0.0"

_CET = timezone(timedelta(hours=2))


def _make(
    model_cls: type[ServiceMetaDataDBCreate | ServiceMetaDataDBPatch],
    **overrides,
) -> ServiceMetaDataDBCreate | ServiceMetaDataDBPatch:
    params: dict = {
        "key": _KEY,
        "version": _VERSION,
        "name": "isolve",
        "description": "iSolve",
    }
    params.update(overrides)
    return model_cls.model_validate(params)


@pytest.mark.parametrize(
    "model_cls",
    [pytest.param(ServiceMetaDataDBCreate, id="Create"), pytest.param(ServiceMetaDataDBPatch, id="Patch")],
)
@pytest.mark.parametrize(
    "given, expected",
    [
        pytest.param(None, None, id="none"),
        # naive timestamps are the ones stored in the column before it became `timestamptz`
        pytest.param(
            datetime(2099, 1, 19, 12, 45),  # noqa: DTZ001
            datetime(2099, 1, 19, 12, 45, tzinfo=UTC),
            id="naive-interpreted-as-utc",
        ),
        pytest.param(
            datetime(2099, 1, 19, 12, 45, tzinfo=UTC),
            datetime(2099, 1, 19, 12, 45, tzinfo=UTC),
            id="utc-unchanged",
        ),
        # an aware value must keep pointing to the same instant
        pytest.param(
            datetime(2099, 1, 19, 14, 45, tzinfo=_CET),
            datetime(2099, 1, 19, 12, 45, tzinfo=UTC),
            id="offset-converted-to-utc",
        ),
    ],
)
def test_deprecated_is_bound_as_utc(model_cls, given, expected):
    # `deprecated` lands in a `timestamptz` column: asyncpg would encode a naive
    # value with the host local timezone, so the models must always yield UTC-aware values
    model = _make(model_cls, deprecated=given)
    assert model.deprecated == expected
    if expected is not None:
        assert model.deprecated is not None
        assert model.deprecated.tzinfo == UTC

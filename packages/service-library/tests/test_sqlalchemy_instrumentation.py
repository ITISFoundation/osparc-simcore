from types import SimpleNamespace
from typing import cast

from pytest_mock import MockerFixture
from servicelib.sqlalchemy_instrumentation import instrument_async_engine
from servicelib.tracing import TracingConfig
from settings_library.tracing import TracingSettings
from sqlalchemy.ext.asyncio import AsyncEngine


def test_instrument_async_engine_happy_path(mocker: MockerFixture):
    sync_engine = object()
    engine = cast(AsyncEngine, SimpleNamespace(sync_engine=sync_engine))

    tracing_settings = TracingSettings(
        TRACING_OPENTELEMETRY_COLLECTOR_ENDPOINT="http://localhost",
        TRACING_OPENTELEMETRY_COLLECTOR_PORT=4317,
        TRACING_OPENTELEMETRY_SAMPLING_PROBABILITY=1.0,
    )
    tracing_config = TracingConfig.create(tracing_settings=tracing_settings, service_name="test-service")

    instrumentor_instance = mocker.Mock()
    instrumentor_cls = mocker.patch(
        "servicelib.sqlalchemy_instrumentation.SQLAlchemyInstrumentor",
        return_value=instrumentor_instance,
    )

    result = instrument_async_engine(engine, tracing_config=tracing_config)

    assert result is engine
    instrumentor_cls.assert_called_once_with()
    instrumentor_instance.instrument.assert_called_once_with(
        engine=sync_engine,
        enable_commenter=False,
        tracer_provider=tracing_config.tracer_provider,
    )


def test_instrument_async_engine_when_tracing_disabled(mocker: MockerFixture):
    sync_engine = object()
    engine = cast(AsyncEngine, SimpleNamespace(sync_engine=sync_engine))
    tracing_config = TracingConfig.create(tracing_settings=None, service_name="test-service")

    instrumentor_cls = mocker.patch("servicelib.sqlalchemy_instrumentation.SQLAlchemyInstrumentor")

    result = instrument_async_engine(engine, tracing_config=tracing_config)

    assert result is engine
    instrumentor_cls.assert_not_called()


def test_instrument_async_engine_when_tracing_config_is_none(mocker: MockerFixture):
    sync_engine = object()
    engine = cast(AsyncEngine, SimpleNamespace(sync_engine=sync_engine))

    instrumentor_cls = mocker.patch("servicelib.sqlalchemy_instrumentation.SQLAlchemyInstrumentor")

    result = instrument_async_engine(engine, tracing_config=None)

    assert result is engine
    instrumentor_cls.assert_not_called()

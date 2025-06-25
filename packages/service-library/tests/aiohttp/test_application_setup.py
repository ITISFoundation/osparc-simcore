# pylint: disable=protected-access
# pylint: disable=redefined-outer-name
# pylint: disable=too-many-arguments
# pylint: disable=unused-argument
# pylint: disable=unused-variable


from collections.abc import Callable

import pytest
from aiohttp import web
from pytest_mock import MockerFixture, MockType
from servicelib.aiohttp.application_keys import APP_CONFIG_KEY
from servicelib.aiohttp.application_setup import (
    DependencyError,
    ModuleCategory,
    SkipModuleSetupError,
    app_module_setup,
    ensure_single_setup,
    is_setup_completed,
)


@pytest.fixture
def mock_logger(mocker: MockerFixture) -> MockType:
    return mocker.patch("logging.getLogger", autospec=True)


@pytest.fixture
def app_config() -> dict:
    return {
        "foo": {"enabled": True},
        "bar": {"enabled": False},
        "main": {"zee_enabled": True},
    }


@pytest.fixture
def app(app_config) -> web.Application:
    _app = web.Application()
    _app[APP_CONFIG_KEY] = app_config
    return _app


@pytest.fixture
def create_setup_bar() -> Callable[[web.Application, str, bool], bool]:
    @app_module_setup("package.bar", ModuleCategory.ADDON)
    def _setup_bar(
        app: web.Application, arg1: str, *, raise_skip: bool = False
    ) -> bool:
        return True

    return _setup_bar


@pytest.fixture
def create_setup_foo() -> Callable[[web.Application, str, bool], bool]:
    @app_module_setup("package.foo", ModuleCategory.ADDON)
    def _setup_foo(
        app: web.Application, arg1: str, *, raise_skip: bool = False, **kwargs
    ) -> bool:
        if raise_skip:
            raise SkipModuleSetupError(reason="explicit skip")
        return True

    return _setup_foo


@pytest.fixture
def create_setup_zee() -> Callable[[web.Application, str, int], bool]:
    @app_module_setup(
        "package.zee", ModuleCategory.ADDON, config_enabled="main.zee_enabled"
    )
    def _setup_zee(app: web.Application, arg1: str, kargs: int = 55) -> bool:
        return True

    return _setup_zee


@pytest.fixture
def create_setup_needs_foo() -> Callable[[web.Application, str, int], bool]:
    @app_module_setup(
        "package.needs_foo",
        ModuleCategory.SYSTEM,
        depends=[
            "package.foo",
        ],
    )
    def _setup_needs_foo(app: web.Application, arg1: str, kargs: int = 55) -> bool:
        return True

    return _setup_needs_foo


def setup_basic(app: web.Application) -> bool:
    return True


def setup_that_raises(app: web.Application) -> bool:
    error_msg = "Setup failed"
    raise ValueError(error_msg)


def test_setup_config_enabled(
    app_config: dict, app: web.Application, create_setup_zee: Callable
):
    setup_zee = create_setup_zee()

    assert setup_zee(app, 1)
    assert setup_zee.metadata()["config_enabled"] == "main.zee_enabled"
    app_config["main"]["zee_enabled"] = False
    assert not setup_zee(app, 2)


def test_setup_dependencies(
    app: web.Application,
    create_setup_needs_foo: Callable,
    create_setup_foo: Callable,
) -> None:
    setup_needs_foo = create_setup_needs_foo()
    setup_foo = create_setup_foo()

    with pytest.raises(DependencyError):
        setup_needs_foo(app, "1")

    assert setup_foo(app, "1")
    assert setup_needs_foo(app, "2")

    assert setup_needs_foo.metadata()["dependencies"] == [
        setup_foo.metadata()["module_name"],
    ]


def test_marked_setup(
    app_config: dict, app: web.Application, create_setup_foo: Callable
):
    setup_foo = create_setup_foo()

    assert setup_foo(app, 1)
    assert setup_foo.metadata()["module_name"] == "package.foo"
    assert is_setup_completed(setup_foo.metadata()["module_name"], app)

    app_config["foo"]["enabled"] = False
    assert not setup_foo(app, 2)


def test_skip_setup(
    app: web.Application, mock_logger: MockType, create_setup_foo: Callable
):
    setup_foo = create_setup_foo()
    assert not setup_foo(app, 1, raise_skip=True)
    assert setup_foo(app, 1)
    mock_logger.info.assert_called()


def test_ensure_single_setup_runs_once(app: web.Application, mock_logger: Mock) -> None:
    decorated = ensure_single_setup("test.module", logger=mock_logger)(setup_basic)

    # First call succeeds
    assert decorated(app)
    assert is_setup_completed("test.module", app)

    # Second call skips
    assert not decorated(app)
    mock_logger.info.assert_called_with(
        "Skipping '%s' setup: %s",
        "test.module",
        "'test.module' was already initialized in <Application. Avoid logging objects like this>. Setup can only be executed once per app.",
    )


def test_ensure_single_setup_error_handling(
    app: web.Application, mock_logger: Mock
) -> None:
    decorated = ensure_single_setup("test.error", logger=mock_logger)(setup_that_raises)

    with pytest.raises(ValueError, match="Setup failed"):
        decorated(app)
    assert not is_setup_completed("test.error", app)


def test_ensure_single_setup_multiple_modules(
    app: web.Application, mock_logger: Mock
) -> None:
    decorated1 = ensure_single_setup("module1", logger=mock_logger)(setup_basic)
    decorated2 = ensure_single_setup("module2", logger=mock_logger)(setup_basic)

    assert decorated1(app)
    assert decorated2(app)
    assert is_setup_completed("module1", app)
    assert is_setup_completed("module2", app)

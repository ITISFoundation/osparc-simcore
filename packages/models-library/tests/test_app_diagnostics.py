from models_library.app_diagnostics import AppStatusCheck


def test_annotated_defaults_and_default_factories():

    model = AppStatusCheck(app_name="foo", version="1.2.3")
    assert model.app_name == "foo"
    assert model.version == "1.2.3"

    # checks default_factory
    assert model.services == {}
    assert model.sessions == {}

    # checks default inside Annotated[, Field(default=None, ...)]
    assert model.url is None

    # checks default outside Annotated
    assert model.diagnostics_url is None

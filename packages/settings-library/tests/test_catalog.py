from settings_library.catalog import CatalogSettings


def test_catalog_settings() -> None:
    settings = CatalogSettings()
    assert settings.base_url == "http://catalog:8000"
    assert settings.api_base_url == "http://catalog:8000/v0"

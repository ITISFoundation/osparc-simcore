from pydantic import TypeAdapter
from simcore_service_api_server.models.pagination import Page


def test_page_serialization_schema_keeps_links_required_for_generated_clients():
    schema = TypeAdapter(Page[int]).json_schema(mode="serialization")

    assert "links" in schema["required"]

    links_schema_name = schema["properties"]["links"]["$ref"].rsplit("/", maxsplit=1)[-1]
    assert set(schema["$defs"][links_schema_name]["required"]) == {
        "first",
        "last",
        "next",
        "prev",
        "self",
    }

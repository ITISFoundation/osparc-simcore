from models_library.api_schemas_webserver.licensed_items import LicensedItemRestGet
from models_library.licenses import LicensedItem
from pydantic import ConfigDict


def test_licensed_item_from_domain_model():
    for example in LicensedItem.model_json_schema()["examples"]:
        item = LicensedItem.model_validate(example)

        got = LicensedItemRestGet.from_domain_model(item)

        assert item.display_name == got.display_name

        # nullable doi
        assert (
            got.licensed_resource_data.source.doi
            == item.licensed_resource_data["source"]["doi"]
        )

        # date is required
        assert got.licensed_resource_data.source.features["date"]

        #
        assert (
            got.licensed_resource_data.source.id
            == item.licensed_resource_data["source"]["id"]
        )


def test_strict_check_of_examples():
    class TestLicensedItemRestGet(LicensedItemRestGet):
        model_config = ConfigDict(extra="forbid")

    for example in LicensedItemRestGet.model_json_schema()["examples"]:
        TestLicensedItemRestGet.model_validate(example)

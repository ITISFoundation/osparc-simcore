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
            got.licensed_resources[0].source.doi
            == item.licensed_resources[0]["source"]["doi"]
        )

        # date is required
        assert got.licensed_resources[0].source.features["date"]

        # id is required
        assert (
            got.licensed_resources[0].source.id
            == item.licensed_resources[0]["source"]["id"]
        )

        # checks unset fields
        assert "category_icon" not in got.licensed_resources[0].model_fields_set


def test_strict_check_of_examples():
    class TestLicensedItemRestGet(LicensedItemRestGet):
        model_config = ConfigDict(extra="forbid")

    for example in LicensedItemRestGet.model_json_schema()["examples"]:
        TestLicensedItemRestGet.model_validate(example)

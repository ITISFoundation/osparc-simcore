from models_library.api_schemas_webserver.licensed_items import LicensedItemRestGet
from models_library.licenses import LicensedItem


def test_licensed_item_from_domain_model():
    for example in LicensedItem.model_json_schema()["examples"]:
        example["licensed_resource_data"]["source"]["doi"] = None

        item = LicensedItem.model_validate(example)
        payload = LicensedItemRestGet.from_domain_model(item)

        assert item.display_name == payload.display_name
        assert (
            item.licensed_resource_data["source"]["doi"]
            == payload.licensed_resource_data.source.doi
        )

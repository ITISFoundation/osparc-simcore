# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable

from pathlib import Path


def test_validation_data_follows_definition(
    label_cfg: dict, validation_cfg: dict, validation_folder: Path
):

    for key, value in label_cfg.items():
        assert "type" in value

        # rationale: files are on their own and other types are in inputs.json
        if not "data:" in value["type"]:
            # check that keys are available
            assert key in validation_cfg
        else:
            # it's a file and it should be in the folder as well using key as the filename
            filename_to_look_for = key
            if "fileToKeyMap" in value:
                # ...or there is a mapping
                assert len(value["fileToKeyMap"]) > 0
                for filename, mapped_value in value["fileToKeyMap"].items():
                    assert mapped_value == key
                    filename_to_look_for = filename
                    assert (validation_folder / filename_to_look_for).exists()
            else:
                assert (validation_folder / filename_to_look_for).exists()

    if validation_cfg:
        for key, value in validation_cfg.items():
            # check the key is defined in the labels
            assert key in label_cfg
            label2types = {
                "number": (float, int),
                "integer": int,
                "boolean": bool,
                "string": str,
            }
            if not "data:" in label_cfg[key]["type"]:
                # check the type is correct
                assert isinstance(value, label2types[label_cfg[key]["type"]])

# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable

from simcore_service_catalog.utils.versioning import is_patch_release


def test_is_patch_check():

    assert is_patch_release("1.0.4", "1.0.3")
    assert is_patch_release("1.0.5", "1.0.3")

    # 1.0.4 is a patch release from 1.0.3 but NOT the reverse
    assert not is_patch_release("1.0.3", "1.0.4")

    # same version
    assert not is_patch_release("1.0.3", "1.0.3")

    # major and minor releases
    assert not is_patch_release("1.1.4", "1.0.3")
    assert not is_patch_release("2.0.4", "1.0.3")

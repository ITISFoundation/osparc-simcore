# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable

from pathlib import Path

from service_integration.oci_image_spec import (
    LabelSchemaAnnotations,
    OCIImageSpecAnnotations,
)
from service_integration.osparc_config import MetaConfig


def test_create_annotations_from_metadata(tests_data_dir: Path):
    # metadata -> produce annotations
    # inject as docker labels
    # recover from docker labels
    #

    meta_cfg = MetaConfig.from_yaml(tests_data_dir / "metadata.yml")

    # map io_spec to OCI image-spec
    oic_image_spec = OCIImageSpecAnnotations(
        authors=", ".join([f"{a.name} ({a.email})" for a in meta_cfg.authors])
    )

    # TODO: convert oic to ls
    ls_spec = LabelSchemaAnnotations()

    # a base image could contain already annotations
    # retrieve from labels
    # override option or merge/append?
    # NOTE: license has a merge language
    #

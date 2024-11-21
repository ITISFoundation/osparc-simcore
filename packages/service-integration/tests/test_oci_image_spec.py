# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable

from pathlib import Path

from service_integration.oci_image_spec import (
    LabelSchemaAnnotations,
    OciImageSpecAnnotations,
)
from service_integration.osparc_config import MetadataConfig


def test_label_schema_to_oci_conversion(monkeypatch):
    monkeypatch.setenv("BUILD_DATE", "2021-11-16T20:02:57Z")
    monkeypatch.setenv("VCS_REF", "34e1f204a")
    monkeypatch.setenv("VCS_URL", "http://github.com/ITISFoundation/osparc-simcore")

    lsa = LabelSchemaAnnotations.create_from_env()

    OciImageSpecAnnotations.model_validate(lsa.to_oci_data())


def test_create_annotations_from_metadata(tests_data_dir: Path):
    # metadata -> produce annotations
    # inject as docker labels
    # recover from docker labels
    #

    meta_cfg = MetadataConfig.from_yaml(tests_data_dir / "metadata.yml")

    # map io_spec to OCI image-spec
    OciImageSpecAnnotations(
        authors=", ".join([f"{a.name} ({a.email})" for a in meta_cfg.authors])
    )

    # TODO: convert oic to ls
    # ls_spec = LabelSchemaAnnotations()

    # a base image could contain already annotations
    # retrieve from labels
    # override option or merge/append?
    # NOTE: license has a merge language
    #

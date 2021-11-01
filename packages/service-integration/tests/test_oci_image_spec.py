# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable

from service_integration.oci_image_spec import (
    LabelSchemaAnnotations,
    OCIImageSpecAnnotations,
)


def test_create_annotations_from_metadata():
    # metadata -> produce annotations
    # inject as docker labels
    # recover from docker labels
    #

    # a base image could contain already annotations
    # retrieve from labels
    # override option or merge/append?
    # NOTE: license has a merge language
    #
    raise NotImplementedError

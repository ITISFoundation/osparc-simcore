from pydantic import ByteSize, parse_obj_as
from simcore_service_autoscaling.utils import bytesto


def test_bytesto():
    size_b, size_mib = 314575262000000, 300002347.946167
    assert bytesto(size_b, "m") == size_mib

    # a more reliable alternative
    assert parse_obj_as(ByteSize, size_b).to("mib") == size_mib

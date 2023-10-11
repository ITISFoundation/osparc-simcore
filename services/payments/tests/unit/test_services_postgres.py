# pylint: disable=protected-access
# pylint: disable=redefined-outer-name
# pylint: disable=too-many-arguments
# pylint: disable=unused-argument
# pylint: disable=unused-variable

import pytest


@pytest.mark.xfail()
def test_one_time_payment_annotations_workflow():

    # annotate init
    # annotate ack
    raise NotImplementedError


# errors:
# -  annotate ack -> error
#
# annotate cancel
#

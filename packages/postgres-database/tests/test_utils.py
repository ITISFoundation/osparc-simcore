# pylint: disable=no-value-for-parameter
# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable

from simcore_postgres_database.utils import hide_dict_pass, hide_url_pass
from yarl import URL


def test_hide_url_pass():

    assert (
        hide_url_pass(URL("postgres://username:password@127.0.0.1/myrailsdb"))
        == "postgres://username:********@127.0.0.1/myrailsdb"
    )


def test_hide_dict_pass():

    assert hide_dict_pass({"pass": "foo", "password": "bar"}) == {
        "pass": "********",
        "password": "********",
    }

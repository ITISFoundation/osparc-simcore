#
# SEE https://docs.locust.io/en/stable/quickstart.html
#

import logging
import urllib
import urllib.parse

import locust
from common.base_user import OsparcWebUserBase

_logger = logging.getLogger(__name__)


class WebApiUser(OsparcWebUserBase):
    @locust.task
    def list_latest_services(self):
        base_url = "/v0/catalog/services/-/latest"
        params = {"offset": 20, "limit": 20}

        while True:
            response = self.authenticated_get(base_url, params=params)
            response.raise_for_status()

            page = response.json()

            # Process the current page data here
            next_link = page["_links"].get("next")
            if not next_link:
                break

            # Update base_url and params for the next request
            parsed_next = urllib.parse.urlparse(next_link)
            base_url = parsed_next.path
            params = dict(urllib.parse.parse_qsl(parsed_next.query))

#
# SEE https://docs.locust.io/en/stable/quickstart.html
#
# This script allows testing the maximum RPS against a single endpoint.
# Usage:
#   locust -f deployment_max_rps_single_endpoint.py --endpoint /v0/health
#
# If no endpoint is specified, the root endpoint ("/") will be used by default.
#


from collections.abc import Callable

from common.base_user import OsparcWebUserBase
from locust import events, run_single_user, task
from locust.argument_parser import LocustArgumentParser


# Register the custom argument with Locust's parser
@events.init_command_line_parser.add_listener
def _(parser: LocustArgumentParser) -> None:
    parser.add_argument(
        "--endpoint",
        type=str,
        default="/",
        help="The endpoint to test (e.g., /v0/health)",
    )
    parser.add_argument(
        "--http-method",
        type=str,
        default="GET",
        help="The HTTP method to test ('GET', 'POST', 'PUT', 'PATCH' or 'DELETE')",
    )
    parser.add_argument(
        "--body",
        type=str,
        default="",
        help="The optional HTTP body as json string",
    )


class WebApiUser(OsparcWebUserBase):
    @task
    def get_endpoint(self) -> None:
        http_method = self.environment.parsed_options.http_method.lower()
        method = getattr(self, f"authenticated_{http_method}")
        if not isinstance(method, Callable):
            msg = f"Unsupported HTTP method: {http_method}"
            raise TypeError(msg)

        kwargs = {}
        if len(self.environment.parsed_options.body) > 0:
            kwargs["data"] = self.environment.parsed_options.body
        method(self.environment.parsed_options.endpoint, **kwargs)


if __name__ == "__main__":
    run_single_user(WebApiUser)

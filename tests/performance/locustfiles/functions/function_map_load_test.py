#
# SEE https://docs.locust.io/en/stable/quickstart.html
#
# This script allows testing running a function via the map endpoint
#


import json
import random
from datetime import timedelta
from typing import Final
from urllib.parse import urlencode
from uuid import UUID

import jsf
from common.base_user import OsparcWebUserBase
from locust import events, task
from locust.argument_parser import LocustArgumentParser
from tenacity import (
    Retrying,
    retry_if_exception_type,
    stop_after_delay,
    wait_exponential,
)

_MAX_NJOBS: Final[int] = 50
_REQUEST_TIMEOUT: Final[int] = 10 * 60  # 10 minutes request timeout for map endpoint


# Register the custom argument with Locust's parser
@events.init_command_line_parser.add_listener
def _(parser: LocustArgumentParser) -> None:
    parser.add_argument(
        "--function-uuid",
        type=UUID,
        default=None,
        help="The function UUID to test",
    )
    parser.add_argument(
        "--function-input-json-schema",
        type=str,
        default=None,
        help="JSON schema for the function job inputs",
    )
    parser.add_argument(
        "--max-poll-time-seconds",
        type=int,
        default=60,
        help="Maximum time to wait for the function job collection to complete",
    )
    parser.add_argument(
        "--n-jobs",
        type=int,
        default=None,
        help=f"Number of jobs to run via map-endpoint. If not set, a random number between 0 and {_MAX_NJOBS} is selected",
    )


class WebApiUser(OsparcWebUserBase):
    network_timeout = _REQUEST_TIMEOUT
    connection_timeout = _REQUEST_TIMEOUT

    @task
    def map_function(self) -> None:
        function_uuid = self.environment.parsed_options.function_uuid
        if function_uuid is None:
            raise ValueError("function-uuid argument is required")
        if self.environment.parsed_options.function_input_json_schema is None:
            raise ValueError("function-input-json-schema argument is required")
        job_input_schema = json.loads(self.environment.parsed_options.function_input_json_schema)
        max_poll_time = timedelta(seconds=self.environment.parsed_options.max_poll_time_seconds)
        n_jobs = (
            int(self.environment.parsed_options.n_jobs)
            if self.environment.parsed_options.n_jobs is not None
            else random.randint(1, _MAX_NJOBS)
        )

        # map function
        job_input_faker = jsf.JSF(job_input_schema)
        response = self.authenticated_post(
            url=f"/v0/functions/{function_uuid}:map",
            json=[job_input_faker.generate() for _ in range(n_jobs)],
            headers={
                "x-simcore-parent-project-uuid": "null",
                "x-simcore-parent-node-id": "null",
            },
            name="/v0/functions/[function_uuid]:map",
        )
        response.raise_for_status()
        job_collection_uuid = response.json().get("uid")

        # wait for the job to complete
        query_params = dict(include_status=True, function_job_collection_id=job_collection_uuid)
        for attempt in Retrying(
            stop=stop_after_delay(max_delay=max_poll_time),
            wait=wait_exponential(multiplier=1, min=1, max=10),
            reraise=True,
            retry=retry_if_exception_type(ValueError),
        ):
            with attempt:
                # list all jobs in the collection with status
                next_page_url = "/v0/function_jobs?" + urlencode(query_params)
                all_job_statuses = []
                while next_page_url is not None:
                    response = self.authenticated_get(
                        next_page_url,
                        name="/v0/function_jobs",
                    )
                    response.raise_for_status()
                    items = response.json().get("items", [])
                    statuses = [item.get("status", {}) for item in items]
                    all_job_statuses.extend([status.get("status", None) for status in statuses if status])
                    assert not any(status is None for status in all_job_statuses), (
                        f"Test misconfiguration: Function job collection ({job_collection_uuid=}) listed {statuses=} with missing status"
                    )
                    links = response.json().get("links", {})
                    assert isinstance(links, dict)
                    next_page_url = links.get("next", None)
                assert len(all_job_statuses) == n_jobs, (
                    f"Expected {n_jobs} jobs, got {len(all_job_statuses)} for {job_collection_uuid=}"
                )

                if any(status != "SUCCESS" for status in all_job_statuses):
                    raise ValueError(
                        f"Function job ({job_collection_uuid=}) for function ({function_uuid=}) returned {all_job_statuses=}"
                    )

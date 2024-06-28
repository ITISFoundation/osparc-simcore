from locust import HttpUser
from urllib3 import PoolManager, Retry


class MetaModelingUser(HttpUser):
    def __init__(self, *args, **kwargs):
        retry_strategy = Retry(
            total=4,
            backoff_factor=4.0,
            status_forcelist={429, 503, 504},
            allowed_methods={
                "DELETE",
                "GET",
                "HEAD",
                "OPTIONS",
                "PUT",
                "TRACE",
                "POST",
                "PATCH",
                "CONNECT",
            },
            respect_retry_after_header=True,
            raise_on_status=True,
        )
        super().__init__(
            *args, **kwargs, pool_manager=PoolManager(key_retries=retry_strategy)
        )

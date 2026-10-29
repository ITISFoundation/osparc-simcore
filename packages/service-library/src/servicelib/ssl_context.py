import functools
import ssl

from httpx2 import create_ssl_context


@functools.lru_cache(maxsize=1)
def get_shared_ssl_context() -> ssl.SSLContext:
    """Shared SSL context for clients that are created and discarded often.

    `httpx2.AsyncClient` builds one eagerly on construction, even for plain
    http:// targets, and parsing the CA bundle costs ~3MB per client.
    Delegates to httpx2 so its default trust store stays unchanged: the system
    certificate store, with SSL_CERT_FILE/SSL_CERT_DIR overrides.
    """
    return create_ssl_context()

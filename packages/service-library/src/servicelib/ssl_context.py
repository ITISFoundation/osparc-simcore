import functools
import ssl

from httpx import create_ssl_context


@functools.lru_cache(maxsize=1)
def get_shared_ssl_context() -> ssl.SSLContext:
    """Shared SSL context for clients that are created and discarded often.

    `httpx.AsyncClient` builds one eagerly on construction, even for plain
    http:// targets, and parsing the CA bundle costs ~3MB per client.
    Delegates to httpx so its default trust store (certifi and the
    SSL_CERT_FILE/SSL_CERT_DIR overrides) stays unchanged.
    """
    return create_ssl_context()

from dataclasses import dataclass
from typing import Final

from sqlalchemy.ext.asyncio import AsyncEngine

## Memory Usage of aiocache for Session Authentication Caching
AUTH_SESSION_TTL_SECONDS: Final = 120  # 2 minutes
"""
    ### Memory Usage Characteristics

    **aiocache** uses in-memory storage by default, which means:

    1. **Linear memory growth**: Each cached item consumes RAM proportional to the serialized size of the cached data
    2. **No automatic memory limits**: By default, there's no built-in maximum memory cap
    3. **TTL-based cleanup**: Items are only removed when they expire (TTL) or are explicitly deleted


    **Key limitations:**
    - **MEMORY backend**: No built-in memory limits or LRU eviction
    - **Maximum capacity**: Limited only by available system RAM
    - **Risk**: Memory leaks if TTL is too long or cache keys grow unbounded

    ### Recommendations for Your Use Case

    **For authentication caching:**

    1. **Low memory impact**: User authentication data is typically small (user_id, email, product_name)
    2. **Short TTL**: Your 120s TTL helps prevent unbounded growth
    3. **Bounded key space**: API keys are finite, not user-generated

    **Memory estimation:**
    ```
    Per cache entry ≈ 200-500 bytes (user data + overhead)
    1000 active users ≈ 500KB
    10000 active users ≈ 5MB
    ```

    ### Alternative Approaches

    **If memory becomes a concern:**

    1. **Redis backend**:
    ```python
    cache = Cache(Cache.REDIS, endpoint="redis://localhost", ...)
    ```

    2. **Custom eviction policy**: Implement LRU manually or use shorter TTL

    3. **Monitoring**: Track cache size in production:
    ```python
    # Check cache statistics
    cache_stats = await cache.get_stats()
    ```

    **Verdict**:
    For authentication use case with reasonable user counts (<10K active), memory impact should be minimal with your current TTL configuration.
"""


@dataclass
class BaseRepository:
    """
    Repositories are pulled at every request
    """

    db_engine: AsyncEngine

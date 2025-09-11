# Redis Lua Scripts for Distributed Semaphore

This directory contains atomic Lua scripts for Redis-based distributed semaphore operations.

## Scripts

### `acquire_semaphore.lua`
Atomically acquire a distributed semaphore slot.

**Parameters:**
- `KEYS[1]`: semaphore_key (ZSET storing holders with timestamps)
- `KEYS[2]`: holder_key (individual holder TTL key)
- `ARGV[1]`: instance_id
- `ARGV[2]`: capacity (max concurrent holders)
- `ARGV[3]`: ttl_seconds

**Returns:** `{success, status, current_count, expired_count}`
- `success`: 1 if acquired, 0 if failed
- `status`: 'acquired' or 'capacity_full'
- `current_count`: number of holders after operation
- `expired_count`: number of expired entries cleaned up

**Note:** Redis TIME is called internally for clock synchronization.

### `count_semaphore.lua`
Atomically count current semaphore holders (with cleanup).

**Parameters:**
- `KEYS[1]`: semaphore_key (ZSET storing holders with timestamps)
- `ARGV[1]`: ttl_seconds

**Returns:** `{current_count, expired_count}`
- `current_count`: number of active holders after cleanup
- `expired_count`: number of expired entries cleaned up

**Note:** Redis TIME is called internally for clock synchronization.

### `renew_semaphore.lua`
Atomically renew a distributed semaphore holder's TTL.

**Parameters:**
- `KEYS[1]`: semaphore_key (ZSET storing holders with timestamps)
- `KEYS[2]`: holder_key (individual holder TTL key)
- `ARGV[1]`: instance_id
- `ARGV[2]`: ttl_seconds

**Returns:** `{success, status, current_count, expired_count}`
- `success`: 1 if renewed, 0 if failed
- `status`: 'renewed', 'not_held', or 'expired'
- `current_count`: number of holders after operation
- `expired_count`: number of expired entries cleaned up

**Note:** Redis TIME is called internally for clock synchronization.

### `release_semaphore.lua`
Atomically release a distributed semaphore slot.

**Parameters:**
- `KEYS[1]`: semaphore_key (ZSET storing holders with timestamps)
- `KEYS[2]`: holder_key (individual holder TTL key)
- `ARGV[1]`: instance_id
- `ARGV[2]`: ttl_seconds

**Returns:** `{success, status, current_count, expired_count}`
- `success`: 1 if released, 0 if failed
- `status`: 'released', 'not_held', or 'already_expired'
- `current_count`: number of holders after operation
- `expired_count`: number of expired entries cleaned up

## Benefits of Lua Scripts

1. **Atomicity**: All operations within a script are atomic
2. **Performance**: Scripts run server-side, reducing network round-trips
3. **Consistency**: Eliminates race conditions between Redis operations
4. **Reliability**: Server-side execution ensures operations complete or fail as a unit

## Usage

These scripts are loaded and executed by the `DistributedSemaphore` class in `_semaphore.py`.
They can be pre-loaded to Redis using `SCRIPT LOAD` and executed with `EVALSHA` for optimal performance.

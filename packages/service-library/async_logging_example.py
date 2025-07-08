#!/usr/bin/env python3

"""
Example demonstrating the new async logging functionality.
This shows how to use both the context manager and manual setup/shutdown approaches.
"""

import asyncio
import logging
import sys
from pathlib import Path

from servicelib.logging_utils import (
    async_logging_context,
    setup_async_loggers,
    shutdown_async_loggers,
)

# Add the servicelib to the path
sys.path.insert(0, str(Path(__file__).parent / "src"))


async def example_with_context_manager():
    """Example using the async context manager approach."""
    print("\n=== Example 1: Using async context manager ===")

    async with async_logging_context(log_format_local_dev_enabled=True):
        logger = logging.getLogger("example1")
        logger.setLevel(logging.DEBUG)

        logger.info("Starting non-blocking async logging example")

        # Simulate some async work with logging
        for i in range(5):
            logger.debug(f"Processing item {i}")
            await asyncio.sleep(0.1)  # Simulate async work

        logger.info("Completed async work")


async def example_with_manual_setup():
    """Example using manual setup and shutdown."""
    print("\n=== Example 2: Using manual setup/shutdown ===")

    # Setup async logging
    await setup_async_loggers(log_format_local_dev_enabled=True)

    try:
        logger = logging.getLogger("example2")
        logger.setLevel(logging.DEBUG)

        logger.info("Starting manual async logging example")

        # Simulate some async work with logging
        tasks = []
        for i in range(3):
            tasks.append(worker_task(f"worker-{i}"))

        await asyncio.gather(*tasks)

        logger.info("All workers completed")

    finally:
        # Always shutdown to ensure clean cleanup
        await shutdown_async_loggers()


async def worker_task(name: str):
    """Simulate a worker task that logs messages."""
    logger = logging.getLogger(f"worker.{name}")

    logger.info(f"{name} starting work")
    await asyncio.sleep(0.2)  # Simulate work
    logger.debug(f"{name} processing data")
    await asyncio.sleep(0.1)
    logger.info(f"{name} work completed")


async def main():
    """Run both examples."""
    print("Async Logging Examples")
    print("=====================")

    # Example 1: Context manager (recommended)
    await example_with_context_manager()

    # Small delay between examples
    await asyncio.sleep(0.5)

    # Example 2: Manual setup/shutdown
    await example_with_manual_setup()

    print("\n=== All examples completed ===")


if __name__ == "__main__":
    asyncio.run(main())

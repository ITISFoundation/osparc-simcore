from datetime import timedelta

# distributed event queue where I push stuff in and have multiple subscribers but only 1 consumes it
# handlers must confirm the event was handled before doing something else with it
# raise an error if they return none instead of True or False
# handlers have to be safe otherwise this will not work, give up after X retries with handling the event from the queue


class DistributedTimer:
    def subscribe(self, periodic_distributed_call: str, interval: timedelta) -> None:
        ...


async def test_distributed_timer():
    distributed_timer = DistributedTimer()

    ...

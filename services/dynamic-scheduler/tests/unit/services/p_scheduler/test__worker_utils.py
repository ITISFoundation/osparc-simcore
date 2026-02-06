from simcore_service_dynamic_scheduler.services.p_scheduler._worker_utils import ChangeNotifier


async def test_change_notifier() -> None:
    notifier = ChangeNotifier[str]()

    calls: list[str] = []

    async def handler1(payload: str) -> None:
        calls.append(f"handler1-{payload}")

    async def handler2(payload: str) -> None:
        calls.append(f"handler2-{payload}")

    # subscribe handlers
    await notifier.subscribe(handler1)
    await notifier.subscribe(handler2)

    # notify with payload
    await notifier.notify("payload1")
    assert calls == ["handler1-payload1", "handler2-payload1"]

    # unsubscribe handler1
    await notifier.unsubscribe(handler1)

    # notify again
    await notifier.notify("payload2")
    assert calls == ["handler1-payload1", "handler2-payload1", "handler2-payload2"]

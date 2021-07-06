# def setup(app: FastAPI, settings: DaskConfig) -> None:
#     def on_startup() -> None:
#         DaskClient.create(
#             app,
#             client=Celery(
#                 settings.task_name,
#                 broker=settings.broker_url,
#                 backend=settings.result_backend,
#             ),
#             settings=settings,
#         )

#     async def on_shutdown() -> None:
#         del app.state.dask_client

#     app.add_event_handler("startup", on_startup)
#     app.add_event_handler("shutdown", on_shutdown)

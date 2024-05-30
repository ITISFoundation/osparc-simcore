from fastapi import FastAPI


class Monitor:
    def __init__(self, app: FastAPI) -> None:
        self.app = app

        # NOTE: THIS needs to be distributed only 1 at a time

    async def _check_status(self) -> None:
        pass

from fastapi import APIRouter

router = APIRouter()


@router.get("/health")
def health() -> str:
    # TODO: check what happens inside the task monitor
    return "ciao"

from fastapi import APIRouter

router = APIRouter(prefix="/templates")


@router.post("/{template}:preview")
def preview_template(template: str):
    assert template

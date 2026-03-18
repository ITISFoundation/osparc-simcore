from pydantic import BaseModel


class Content(BaseModel):
    """Base class for all notification content models."""

    @classmethod
    def get_field_names(cls) -> tuple[str, ...]:
        """Get all field names for this content model (used for template parts)."""
        return tuple(cls.model_fields.keys())

# Prompt

```
Please convert all pydantic model fields that use `Field()` with default values to use the Annotated pattern instead.
Follow these guidelines:

1. Move default values outside of `Field()` like this: `field_name: Annotated[field_type, Field(description="")] = default_value`.
2. Keep all other parameters like validation_alias and descriptions inside `Field()`.
3. For fields using default_factory, keep that parameter as is in the `Field()` constructor, but set the default value outside to DEFAULT_FACTORY from common_library.basic_types. Example: `field_name: Annotated[dict_type, Field(default_factory=dict)] = DEFAULT_FACTORY`.
4. Add the import: `from common_library.basic_types import DEFAULT_FACTORY` if it's not already present.
5. If `Field()` has no parameters (empty), don't use Annotated at all. Just use: `field_name: field_type = default_value`.
6. Leave any model validations, `model_config` settings, and `field_validators` untouched.
```
## Examples

### Before:

```python
from pydantic import BaseModel, Field

class UserModel(BaseModel):
    name: str = Field(default="Anonymous", description="User's display name")
    age: int = Field(default=18, ge=0, lt=120)
    tags: list[str] = Field(default_factory=list, description="User tags")
    metadata: dict[str, str] = Field(default_factory=dict)
    is_active: bool = Field(default=True)
```

- **After**

```python
from typing import Annotated
from pydantic import BaseModel, Field
from common_library.basic_types import DEFAULT_FACTORY

class UserModel(BaseModel):
    name: Annotated[str, Field(description="User's display name")] = "Anonymous"
    age: Annotated[int, Field(ge=0, lt=120)] = 18
    tags: Annotated[list[str], Field(default_factory=list, description="User tags")] = DEFAULT_FACTORY
    metadata: Annotated[dict[str, str], Field(default_factory=dict)] = DEFAULT_FACTORY
    is_active: bool = True
```

## Another Example with Complex Fields

### Before:

```python
from pydantic import BaseModel, Field, field_validator
from datetime import datetime

class ProjectModel(BaseModel):
    id: str = Field(default_factory=uuid.uuid4, description="Unique project identifier")
    name: str = Field(default="Untitled Project", min_length=3, max_length=50)
    created_at: datetime = Field(default_factory=datetime.now)
    config: dict = Field(default={"version": "1.0", "theme": "default"})

    @field_validator("name")
    def validate_name(cls, v):
        if v.isdigit():
            raise ValueError("Name cannot be only digits")
        return v
```

### After:

```python
from typing import Annotated
from pydantic import BaseModel, Field, field_validator
from datetime import datetime
from common_library.basic_types import DEFAULT_FACTORY

class ProjectModel(BaseModel):
    id: Annotated[str, Field(default_factory=uuid.uuid4, description="Unique project identifier")] = DEFAULT_FACTORY
    name: Annotated[str, Field(min_length=3, max_length=50)] = "Untitled Project"
    created_at: Annotated[datetime, Field(default_factory=datetime.now)] = DEFAULT_FACTORY
    config: dict = {"version": "1.0", "theme": "default"}

    @field_validator("name")
    def validate_name(cls, v):
        if v.isdigit():
            raise ValueError("Name cannot be only digits")
        return v
```

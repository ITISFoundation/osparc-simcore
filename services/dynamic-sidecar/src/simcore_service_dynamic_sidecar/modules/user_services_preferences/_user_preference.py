from models_library.services import ServiceKey
from models_library.user_preferences import UserServiceUserPreference
from models_library.utils.change_case import snake_to_upper_camel
from pydantic import create_model


def get_model_class(service_key: ServiceKey) -> type[UserServiceUserPreference]:
    base_model_name = snake_to_upper_camel(
        service_key.replace("/", "_").replace("-", "_")
    )
    class_name = f"{base_model_name}UserServiceUserPreference"

    if class_name in UserServiceUserPreference.registered_user_preference_classes:
        return UserServiceUserPreference.registered_user_preference_classes[class_name]
    return create_model(class_name, __base__=UserServiceUserPreference)

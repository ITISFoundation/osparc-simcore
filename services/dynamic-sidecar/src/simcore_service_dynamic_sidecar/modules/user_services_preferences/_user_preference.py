from models_library.services import ServiceKey
from models_library.user_preferences import UserServiceUserPreference
from models_library.utils.change_case import snake_to_upper_camel
from pydantic import create_model


def get_model_class(service_key: ServiceKey) -> type[UserServiceUserPreference]:
    base_model_name = snake_to_upper_camel(
        service_key.replace("/", "_").replace("-", "_")
    )
    model_class_name = f"{base_model_name}UserServiceUserPreference"

    model_type: type[UserServiceUserPreference] = (
        UserServiceUserPreference.registered_user_preference_classes[model_class_name]
        if model_class_name
        in UserServiceUserPreference.registered_user_preference_classes
        else create_model(model_class_name, __base__=UserServiceUserPreference)
    )
    return model_type

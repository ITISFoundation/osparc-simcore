from typing import Annotated, Any, Union, get_args, get_origin


def get_types_from_annotated_union(annotated_alias: Any) -> tuple[type, ...]:
    """
    Introspects a complex Annotated alias to extract the base types from its inner Union.
    """
    if get_origin(annotated_alias) is not Annotated:
        msg = "Expected an Annotated type."
        raise TypeError(msg)

    # Get the contents of Annotated, e.g., (Union[...], Discriminator(...))
    annotated_args = get_args(annotated_alias)
    union_type = annotated_args[0]

    # The Union can be from typing.Union or the | operator
    if get_origin(union_type) is not Union:
        msg = "Expected a Union inside the Annotated type."
        raise TypeError(msg)

    # Get the members of the Union, e.g., (Annotated[TypeA, ...], Annotated[TypeB, ...])
    union_members = get_args(union_type)

    extracted_types = []
    for member in union_members:
        # Each member is also Annotated, so we extract its base type
        if get_origin(member) is Annotated:
            extracted_types.append(get_args(member)[0])
        else:
            extracted_types.append(member)  # Handle non-annotated members in the union

    return tuple(extracted_types)

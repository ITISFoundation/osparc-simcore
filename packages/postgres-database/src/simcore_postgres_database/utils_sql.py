def assemble_array_groups(user_group_ids: list[int]) -> str:
    return (
        "array[]::text[]"
        if len(user_group_ids) == 0
        else f"""array[{', '.join(f"'{group_id}'" for group_id in user_group_ids)}]"""
    )

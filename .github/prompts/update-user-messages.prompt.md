---
mode: 'edit'
description: 'Update user messages'
---

This prompt guide is for updating user-facing messages in ${file} or ${selection}

## What is a User Message?

A user message is any string that will be displayed to end-users of the application.
In our codebase, these messages are marked with the `user_message` function:

```python
from common_library.user_messages import user_message

error_msg = user_message("Operation failed. Please try again later.")
```

## Guidelines for Updating User Messages

When modifying user messages, follow these rules:

1. **Version Tracking**: Every modification to a user message must include an incremented `_version` parameter:

   ```python
   # Before modification
   user_message("Error: Unable to connect to the server.")

   # After modification
   user_message("Error: Cannot establish connection to the server.", _version=1)
   ```

2. **F-String Preservation**: When modifying messages that use f-strings, preserve all parameters and their formatting:

   ```python
   # Before
   user_message(f"Project {project_name} could not be loaded.")

   # After (correct)
   user_message(f"Unable to load project {project_name}.", _version=1)

   # After (incorrect - lost the parameter)
   user_message("Unable to load project.", _version=1)
   ```

3. **Message Style**: Follow the guidelines in `${workspaceFolder}/docs/user-messages-guidelines.md`

4. **Preserve Context**: Ensure the modified message conveys the same meaning and context as the original.

5. **Incremental Versioning**: If a message already has a version, increment it by 1:

   ```python
   # Before
   user_message("Session expired.", _version=2)

   # After
   user_message("Your session has expired. Please log in again.", _version=3)
   ```

## Examples

### Example 1: Simple Message Update

```python
# Before
error_dialog(user_message("Failed to save changes."))

# After
error_dialog(user_message("Failed to save your changes. Please try again.", _version=1))
```

### Example 2: F-string Message Update

```python
# Before
raise ValueError(user_message(f"Invalid input parameter: {param_name}"))

# After
raise ValueError(user_message(f"The parameter '{param_name}' contains an invalid value.", _version=1))
```

### Example 3: Already Versioned Message

```python
# Before
return HttpErrorInfo(status.HTTP_404_NOT_FOUND, user_message("User not found.", _version=1))

# After
return HttpErrorInfo(status.HTTP_404_NOT_FOUND, user_message("The requested user could not be found.", _version=2))
```

Remember: The goal is to improve clarity and helpfulness for end-users while maintaining accurate versioning for tracking changes.

---
mode: 'edit'
description: 'Update user messages'
model: Claude Sonnet 3.5
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

When modifying user messages, follow **as close as possible** these rules:

1. **Version Tracking**: Every modification to a user message must include an incremented `_version` parameter:

   ```python
   # Before modification
   user_message("Error: Unable to connect to the server.")

   # After modification, add _version or increment it if it already exists
   user_message("Currently unable to establish connection to the server.", _version=1)
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

3. **Message Style**: Follow **STRICTLY ALL 10 GUIDELINES** in `${workspaceFolder}/docs/user-messages-guidelines.md`:
   - Be Clear and Concise
   - Provide Specific and Actionable Information
   - Avoid Technical Jargon
   - Use a Polite and Non-Blaming Tone
   - Avoid Negative Words and Phrases
   - Place Messages Appropriately
   - Use Inline Validation When Possible
   - Avoid Using All-Caps and Excessive Punctuation
   - **Use Humor Sparingly** - Avoid casual phrases like "Oops!", "Whoops!", or overly informal language
   - Offer Alternative Solutions or Support

4. **Preserve Context**: Ensure the modified message conveys the same meaning and context as the original.

5. **Incremental Versioning**: If a message already has a version, increment it by 1:

   ```python
   # Before
   user_message("Session expired.", _version=2)

   # After
   user_message("Your session has expired. Please log in again.", _version=3)
   ```

6. **Replace 'Study' by 'Project'**: If the message contains the word 'Study', replace it with 'Project' to align with our terminology.

7. **Professional Tone**: Maintain a professional, helpful tone. Avoid humor, casual expressions, or overly informal language that might not be appropriate for all users or situations.

## Examples

### Example 1: Simple Message Update

```python
# Before
error_dialog(user_message("Failed to save changes in this study."))

# After
error_dialog(user_message("Unable to save your changes in this project.", _version=1))
```

### Example 2: F-string Message Update

```python
# Before
raise ValueError(user_message(f"Invalid input parameter: {param_name}"))

# After
raise ValueError(user_message(f"The parameter '{param_name}' contains a value that is not allowed.", _version=1))
```

### Example 3: Already Versioned Message

```python
# Before
return HttpErrorInfo(status.HTTP_404_NOT_FOUND, user_message("User not found.", _version=1))

# After
return HttpErrorInfo(status.HTTP_404_NOT_FOUND, user_message("The requested user could not be found.", _version=2))
```

### Example 4: Removing Humor (Guideline 9)

```python
# Before
user_message("Oops! Something went wrong, but we've noted it down and we'll sort it out ASAP. Thanks for your patience!")

# After
user_message("Something went wrong on our end. We've been notified and will resolve this issue as soon as possible. Thank you for your patience.", _version=1)
```

Remember: The goal is to improve clarity and helpfulness for end-users while maintaining accurate versioning for tracking changes. **Always check that your updated messages comply with ALL 10 guidelines, especially avoiding humor and maintaining a professional tone.**

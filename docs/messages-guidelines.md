
# Error and Warning Message Guidelines

These guidelines ensure that messages are user-friendly, clear, and helpful while maintaining a professional tone. 🚀

Some details:

- Originated from [guidelines](https://wiki.speag.com/projects/SuperMash/wiki/Concepts/GUI) by @eofli and refined iterating with AI
- Here’s the fully expanded and rewritten list of **error and warning message guidelines**, each with:
  - A **guideline**
  - A **rationale**
  - A ❌ **bad example**
  - A ✅ **good example**
  - A **reference**
- This list is intended to be short enough to be read and understood for humans as well as complete so that it can be used as context for automatic correction of error/warning messages

---

## 1. Be Clear and Concise

- **Guideline:** Use straightforward language to describe the issue without unnecessary words.
- **Rationale:** Users can quickly understand the problem and take corrective action when messages are simple and to the point.
- ❌ **Bad Example:**
  `"An error has occurred due to an unexpected input that couldn't be parsed correctly."`
- ✅ **Good Example:**
  `"We couldn't process your request. Please check your input and try again."`
- **[Reference](https://uxwritinghub.com/error-message-examples/)**

---

## 2. Provide Specific and Actionable Information

- **Guideline:** Clearly state what went wrong and how the user can fix it.
- **Rationale:** Specific guidance helps users resolve issues efficiently, reducing frustration.
- ❌ **Bad Example:**
  `"Something went wrong."`
- ✅ **Good Example:**
  `"Your session has expired. Please log in again to continue."`
- **[Reference](https://www.nngroup.com/articles/error-message-guidelines/)**

---

## 3. Avoid Technical Jargon

- **Guideline:** Use plain language instead of technical terms or codes.
- **Rationale:** Non-technical users may not understand complex terminology, hindering their ability to resolve the issue.
- ❌ **Bad Example:**
  `"Error 429: Too many requests per second."`
- ✅ **Good Example:**
  `"You’ve made too many requests. Please wait a moment and try again."`
- **[Reference](https://cxl.com/blog/error-messages/)**

---

## 4. Use a Polite and Non-Blaming Tone

- **Guideline:** Frame messages in a way that doesn't place blame on the user.
- **Rationale:** A respectful tone maintains a positive user experience and encourages users to continue using the application.
- ❌ **Bad Example:**
  `"You entered the wrong password."`
- ✅ **Good Example:**
  `"The password doesn't match. Please try again."`
- **[Reference](https://atlassian.design/content/writing-guidelines/writing-error-messages/)**

---

## 5. Avoid Negative Words and Phrases

- **Guideline:** Steer clear of words like "error," "failed," "invalid," or "illegal."
- **Rationale:** Positive language reduces user anxiety and creates a more supportive experience.
- ❌ **Bad Example:**
  `"Invalid email address."`
- ✅ **Good Example:**
  `"The email address format doesn't look correct. Please check and try again."`
- **[Reference](https://atlassian.design/content/writing-guidelines/writing-error-messages/)**

---

## 6. Place Messages Appropriately

- **Guideline:** Display error messages near the relevant input field or in a clear, noticeable location.
- **Rationale:** Proper placement ensures users notice the message and understand where the issue occurred.
- ❌ **Bad Example:**
  Showing a generic "Form submission failed" message at the top of the page.
- ✅ **Good Example:**
  Placing "Please enter a valid phone number" directly below the phone input field.
- **[Reference](https://www.smashingmagazine.com/2022/08/error-messages-ux-design/)**

---

## 7. Use Inline Validation When Possible

- **Guideline:** Provide real-time feedback as users interact with input fields.
- **Rationale:** Inline validation allows users to correct errors immediately, enhancing the flow and efficiency of the interaction.
- ❌ **Bad Example:**
  Waiting until form submission to show all validation errors.
- ✅ **Good Example:**
  Displaying "Password must be at least 8 characters" while the user types.
- **[Reference](https://cxl.com/blog/error-messages/)**

---

## 8. Avoid Using All-Caps and Excessive Punctuation

- **Guideline:** Refrain from writing messages in all capital letters or using multiple exclamation marks.
- **Rationale:** All-caps and excessive punctuation can be perceived as shouting, which may frustrate users.
- ❌ **Bad Example:**
  `"INVALID INPUT!!!"`
- ✅ **Good Example:**
  `"This input doesn't look correct. Please check and try again."`
- **[Reference](https://uxwritinghub.com/error-message-examples/)**

---

## 9. Use Humor Sparingly

- **Guideline:** Incorporate light-hearted language only when appropriate and aligned with the application's tone.
- **Rationale:** While humor can ease tension, it may not be suitable for all users or situations and can sometimes be misinterpreted.
- ❌ **Bad Example:**
  `"Oopsie daisy! You broke something!"`
- ✅ **Good Example:**
  `"Something went wrong. Try again, or contact support if the issue continues."`
- **[Reference](https://cxl.com/blog/error-messages/)**

---

## 10. Offer Alternative Solutions or Support

- **Guideline:** If the user cannot resolve the issue independently, provide a way to contact support or access help resources.
- **Rationale:** Offering support options ensures users don't feel stranded and can seek help to resolve their issues.
- ❌ **Bad Example:**
  `"Access denied."`
- ✅ **Good Example:**
  `"You don't have permission to view this page. Contact support if you think this is a mistake."`
- **[Reference](https://learn.microsoft.com/en-us/dynamics365/business-central/dev-itpro/developer/devenv-error-handling-guidelines/)**

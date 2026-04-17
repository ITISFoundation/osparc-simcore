---
name: user-facing-message-style
description: 'Rewrite or create user-facing information, warning, and error messages in a professional, clear, implementation-agnostic style with product-specific terminology. Use when: editing UI copy, API-exposed messages, validation text, information states, warnings, retries, recovery prompts, localization source strings, and support-oriented UX writing.'
---

# User-Facing Message Style Guidelines

Use this skill to rewrite or author user-facing information, warning, and error messages that are clear, actionable, professional, and aligned with product terminology. This skill is implementation-agnostic and applies equally to Python helpers, C++ macros, translation wrappers, UI templates, or plain text resources.

## When to Use

- Rewriting terse or technical messages into user-friendly language
- Standardizing information/warning/error tone across products and modules
- Preserving product-specific terminology during terminology migrations
- Improving validation and recovery text in forms, dialogs, notifications, and APIs

## Scope and Non-Goals

- Scope: user-visible message text, labels, and short supporting hints
- Non-goal: changing business logic or behavior
- Non-goal: exposing internal stack traces, exception classes, request IDs, or implementation details in user-visible text

## Message Rewrite Workflow

### 1. Determine message intent

Classify the message before rewriting:
- Information/status: progress, completion, confirmation, or non-blocking state
- Validation: user input format/constraint
- Permission/access: user lacks rights or role
- Availability/system: temporary backend or network problem
- Conflict/state: action cannot proceed due to current state
- Not found: resource unavailable or moved
- Rate/limits: usage quota or request burst limit reached

### 2. Extract local context around the target text

Use nearby code comments, surrounding UI copy, and function/variable names to infer:
- User goal at that step
- Domain object (project, study, account, simulation, file)
- Allowed next action (retry, edit input, refresh, contact support)

### 3. Preserve domain terminology

Keep repository-approved product terms users recognize.
- If terminology is being migrated, move to preferred term without changing meaning.
- Do not replace known domain terms with generic synonyms when that reduces clarity.

### 4. Build message in 3 parts

- What happened: clear and concrete
- What user can do: immediate next step
- Optional escalation: when to contact support or try alternative path

### 5. Apply tone and formatting constraints

- Professional, neutral, and non-blaming
- No all caps, no repeated punctuation
- Avoid cutesy interjections (for example: oops, whoops)
- Keep sentences short; prefer one or two sentences

### 6. Run completion checks

A rewrite is complete only if all are true:
- First-read comprehension for non-technical users
- Problem is described without internals
- Next action is explicit and feasible
- Intent and scope of the original message are preserved
- Domain terminology remains correct

## Quick Rewrite Checklist

- Can a non-technical user understand it on first read? (see #1 and #3)
- Does it explain the problem without exposing internals? (see #3)
- Does it suggest the next action, retry, or recovery step? (see #2 and #10)
- Does it avoid blaming the user? (see #4 and #5)
- Is it free of all caps and excessive punctuation? (see #8)
- Is the tone appropriate, without misplaced humor? (see #9)
- Does it preserve recognized domain terminology? (see Terminology Notes)
- Does it preserve original intent and scope?

## Typical Transformations

- Invalid input. -> This value does not look correct. Please review it and try again.
- Error 429 -> Too many requests were sent in a short time. Please wait a moment and try again.
- Failed to save study. -> Unable to save this project right now. Please try again.
- Oops! Something broke. -> Something went wrong on our end. Please try again, or contact support if the issue continues.
- Access denied. -> You do not have permission to view this page. Contact support if you think this is a mistake.
- Error 500: NullReferenceException in JobRunner -> We could not complete this action right now. Please try again in a few minutes.
- Data sync completed. -> Your data is up to date.

## Terminology Notes

- Use repository-approved product terms.
- If terms are migrating, update to preferred terms while keeping meaning unchanged.
- Keep diagnostics out of user-facing text unless intentionally exposed.
- If diagnostics are required, separate them into a details section, log metadata, or support context, not main user copy.

## Initial Rewrite Index (Fast Start)

Use this quick path when editing many messages:

1. Identify message type and user goal.
2. Preserve domain terms and legal/compliance constraints.
3. Rewrite to: situation + action + optional escalation.
4. Remove jargon, blame, all caps, and noisy punctuation.
5. Verify first-read clarity and intent preservation.

If ambiguity remains, prefer a neutral recovery message and include a safe next step.

## Base Guidelines

These rules are concise enough for humans and complete enough for automated rewriting.

### Enforcement Policy

- Default mode: Apply all Base Guidelines strictly.
- Reality check: In some scenarios, guidelines can conflict. Resolve conflicts using the priority order below.
- Exception rule: A lower-priority guideline can be relaxed only when required by a higher-priority guideline.
- Documentation rule: If an exception is used, note a short reason in review context (for example: "security exception, avoid account enumeration").

### Conflict-Resolution Priority (Highest to Lowest)

1. Safety, legal, privacy, and security constraints
2. User recovery and actionability
3. Clarity and first-read comprehension
4. Professional, non-blaming tone
5. Formatting and stylistic polish

### Known Conflict Patterns

- Concise vs actionable:
  - Keep message short, but do not remove the next step needed for recovery.
- Plain language vs diagnostic precision:
  - Keep user-facing text plain; put technical codes in optional details.
- Non-blaming tone vs security-sensitive flows:
  - Do not reveal sensitive state (for example, account existence) even if specificity is reduced.
- Near-source placement vs severe system outages:
  - Use global or blocking messaging for catastrophic states; use local inline messages for field-level errors.
- Delayed validation vs early guidance:
  - Avoid premature blame, but allow progressive hints for high-error inputs.

### Compliance Outcome Categories

- Full compliance: All Base Guidelines satisfied.
- Justified exception: One or more lower-priority rules relaxed due to a higher-priority constraint.
- Non-compliant: Violates guidelines without a valid higher-priority reason.

### 1. Be Clear and Concise

- Guideline: Use straightforward language and short sentences.
- Rationale: Short, concrete messages are easier to scan and understand under stress.
- Example 1:
  - Bad: "An error has occurred due to an unexpected input that could not be parsed correctly."
  - Good: "We could not process this value. Please review it and try again."
- Example 2:
  - Bad: "Input mismatch in provided field."
  - Good: "This value does not look correct. Please check and try again."
- Reference: SRC-01

### 2. Provide Specific and Actionable Information

- Guideline: Explain what happened and what to do next.
- Rationale: Users recover faster when next steps are explicit.
- Example 1:
  - Bad: "Something went wrong."
  - Good: "Your session has expired. Please sign in again to continue."
- Example 2:
  - Bad: "Upload failed."
  - Good: "This file is too large. Upload a file smaller than 20 MB."
- Reference: SRC-02

### 3. Avoid Technical Jargon in the Main Message

- Guideline: Prefer plain language over status codes and internal identifiers.
- Rationale: Most users cannot act on technical diagnostics.
- Example 1:
  - Bad: "Error 429: Too many requests per second."
  - Good: "Too many requests were sent in a short time. Please wait a moment and try again."
- Example 2:
  - Bad: "NullReferenceException in JobRunner (E5003)."
  - Good: "We could not complete this action right now. Please try again."
- Reference: SRC-03

### 4. Use a Polite, Non-Blaming Tone

- Guideline: Avoid phrasing that accuses or shames users.
- Rationale: Respectful language reduces frustration and drop-off.
- Example 1:
  - Bad: "You entered the wrong password."
  - Good: "The password does not match. Please try again."
- Example 2:
  - Bad: "You failed to fill all required fields."
  - Good: "Please complete the highlighted fields and try again."
- Reference: SRC-02

### 5. Prefer Constructive Wording Over Negative Labels

- Guideline: Replace harsh terms (invalid, failed, denied) with guidance-oriented phrasing when possible.
- Rationale: Constructive wording keeps users focused on resolution.
- Example 1:
  - Bad: "Invalid email address."
  - Good: "The email format does not look correct. Please check and try again."
- Example 2:
  - Bad: "Failed to complete operation."
  - Good: "We could not complete this action right now. Please retry."
- Reference: SRC-05

### 6. Keep Errors Near the Source and Context-Aware

- Guideline: Place the message where the issue occurred and reference the exact field or object.
- Rationale: Proximity reduces cognitive load and correction time.
- Example 1:
  - Bad: Global banner says "Submission failed" with no field guidance.
  - Good: "Enter a valid email address, for example name@example.com." shown next to the email field.
- Example 2:
  - Bad: Top-page message "Invalid value" with no pointer.
  - Good: "Project name is required." shown directly below the project name input.
- Reference: SRC-02

### 7. Preserve User Effort and Support Recovery

- Guideline: Avoid forcing users to re-enter data; suggest the fastest recovery path.
- Rationale: Preserving progress prevents abandonment and repeated errors.
- Example 1:
  - Bad: "Form submission failed." (all fields reset)
  - Good: "We could not submit this form yet. Your entries are saved. Please fix the highlighted fields and try again."
- Example 2:
  - Bad: "Upload interrupted." (selection lost)
  - Good: "Upload was interrupted. Your selected files are still here. Please try again."
- Reference: SRC-02

### 8. Avoid All Caps and Excessive Punctuation

- Guideline: Do not shout through typography or punctuation.
- Rationale: Aggressive visual tone increases stress and reduces trust.
- Example 1:
  - Bad: "INVALID INPUT!!!"
  - Good: "This input does not look correct. Please check and try again."
- Example 2:
  - Bad: "ERROR: ACCESS DENIED!!"
  - Good: "You do not have permission to view this page."
- Reference: SRC-01

### 9. Use Humor Sparingly and Never at User Expense

- Guideline: Humor is optional and must never reduce clarity or empathy.
- Rationale: In error states, humor can feel dismissive if it blocks recovery.
- Example 1:
  - Bad: "Oopsie daisy! You broke something!"
  - Good: "Something went wrong. Try again, or contact support if the issue continues."
- Example 2:
  - Bad: "Nope. Try harder."
  - Good: "We could not process this request. Please review the highlighted details and try again."
- Reference: SRC-03

### 10. Offer Alternatives or Support Paths

- Guideline: If immediate self-recovery is unlikely, provide a help route.
- Rationale: Users should never feel stuck.
- Example 1:
  - Bad: "Access denied."
  - Good: "You do not have permission to view this page. Contact support if you think this is a mistake."
- Example 2:
  - Bad: "Unable to continue."
  - Good: "Still blocked? Contact support and include this reference code."
- Reference: SRC-05

### 11. Match Severity and Modality to Impact

- Guideline: Use warnings for recoverable situations and blocking dialogs only for hard stops.
- Rationale: Overly severe messaging creates fatigue and desensitization.
- Example 1:
  - Bad: Modal dialog for a non-blocking optional setting.
  - Good: Inline warning for optional preference, blocking dialog for irreversible actions.
- Example 2:
  - Bad: Critical alert for a retryable timeout.
  - Good: Non-blocking notice with retry option for temporary timeout.
- Reference: SRC-02

### 12. Time Messages to Avoid Premature Blame

- Guideline: Do not surface errors before users can reasonably complete input.
- Rationale: Premature validation feels hostile and confusing.
- Example 1:
  - Bad: "This field is required" as soon as a user focuses and blurs an untouched optional section.
  - Good: Validate on submit or after meaningful interaction; use progressive inline hints for known error-prone inputs.
- Example 2:
  - Bad: Showing five required-field errors before first submit.
  - Good: Show focused inline guidance as each required field is completed.
- Reference: SRC-02

## Context-Aware Rewrite Patterns

Use nearby context to refine wording without changing behavior:

- If comments indicate transient backend issues:
  - Use temporary language ("right now", "please try again in a moment").
- If code path is permission-related:
  - Mention access level and support contact path.
- If retries are safe/idempotent:
  - Include explicit retry guidance.
- If action is irreversible:
  - Use clear warning with consequence-first wording.
- If data was preserved:
  - Tell users their progress is kept.

## Decision Points and Branching

- Can user fix it directly now?
  - Yes: give exact corrective step.
  - No: provide support or alternative workflow.
- Is root cause internal/transient?
  - Yes: avoid user blame; propose retry window.
- Is this security-sensitive?
  - Yes: avoid revealing account existence or sensitive details.
- Is there a known one-step remediation?
  - Yes: phrase button/action clearly (for example: "Retry", "Update value", "Show settings").

## Quality Bar for Completion

A final message must pass:

- Clarity: understandable without technical background
- Actionability: includes a realistic next step
- Professional tone: respectful and non-accusatory
- Terminology: uses approved product vocabulary
- Safety: avoids leaking sensitive internals
- Fidelity: preserves original intent and scope

## External References

- Sources and IDs: [references/sources.yaml](./references/sources.yaml)
- Optional metadata: [references/metadata.yaml](./references/metadata.yaml)

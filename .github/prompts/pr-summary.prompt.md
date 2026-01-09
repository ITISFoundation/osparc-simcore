---
mode: agent
description: Generates a PR summary, suitable for a PR against the current `master` branch.
model: GPT-4.1
---

Generate a concise pull request summary by analyzing the git diff between the current branch and `master`. Follow these guidelines:

## Analysis Requirements
1. **Examine the diff**: Review all changed files, added/removed code, and commit messages
2. **Identify key changes**:
   - User-facing functionality (features, UI changes, bug fixes)
   - API or public interface modifications
   - Architecture or design pattern changes
   - Database schema updates
   - Configuration or environment variable changes
3. **Determine the primary change type** using appropriate gitmoji from the template

## Output Format
Structure your summary following [PULL_REQUEST_TEMPLATE.md](../PULL_REQUEST_TEMPLATE.md):

### Title
- Use appropriate gitmoji prefix (🐛, ✨, ♻️, etc.)
- Be descriptive but concise (max 10 words)

### What do these changes do?
- **Maximum 10 lines**
- Start with a high-level overview (1-2 sentences)
- List specific changes as bullet points
- Focus on **what** changed and **why**, not implementation details
- Mention user-facing impact if applicable

### Related issue/s
- Link related issues using `closes #XXX`, `fixes #XXX`, or `resolves #XXX`
- If no issue exists, write "N/A"

### How to test
- Provide 3-5 clear, actionable steps for reviewers
- Include relevant commands, URLs, or UI navigation
- Mention any setup requirements (env vars, migrations, etc.)

### Dev-ops
- Note if environment variables changed
- Flag database migrations (use 🗃️ in title)
- Indicate if manual testing is needed (use 🚨 in title)
- Mention if ops configuration updates are required (use ⚠️ in title)

## Style Guidelines
- Be precise and factual
- Use active voice and present tense
- Avoid jargon unless necessary
- Keep total length under 30 lines
- Present the final summary in a markdown code block for easy copying

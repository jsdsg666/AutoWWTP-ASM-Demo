# Reflection Agent

Validate the extracted config against the plan.

## Goal

Check that:

- required fields exist
- boundary shape is complete
- target variables match the active model
- parameter subset matches the chosen model
- the config still agrees with the plan

## Rules

- Prefer repair over rejection when the fix is obvious.
- Route back to modeling only when the config is genuinely inconsistent.
- Keep validation concrete and file-backed.

## Output shape

- structured validation result
- retry guidance when needed

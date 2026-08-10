# Modeling Agent

Convert the plan into machine-readable config.

## Goal

Extract:

- `asm_config_before.json`
- `asm_config_after.json`
- `asm_config.json`

## Rules

- Preserve the chosen model and calibration mode.
- Keep only valid target variable names.
- Fill the 6 fixed boundary keys explicitly.
- Do not add extra fields.

## Output shape

- one JSON object
- no prose around the JSON
- no extra code fences beyond the required block

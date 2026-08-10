# Plan Agent

Turn the process context into an ASM plan.

## Goal

Choose and describe:

- `modelcomplex`
- `calibmode`
- `sens_targets`
- `xlsx_path`
- `sens_delta`
- `senstopk`
- `maxiter`
- allowed boundary terms

## Rules

- Keep the plan in prose.
- Use only boundary types explicitly supported by the task.
- Keep the task file content intact inside the plan.
- Do not emit JSON.

## Output shape

- English Markdown
- 11 sections
- concise prose
- no code blocks

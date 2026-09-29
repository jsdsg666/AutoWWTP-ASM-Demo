---
name: autowwtp-asm
description: Use for AutoWWTP-ASM wastewater modeling tasks: understand the task, build an ASM plan, extract runnable config, validate and repair it, run sensitivity/calibration, and generate reports and traces.
---

# AutoWWTP-ASM

Use this project for the standalone AutoWWTP-ASM modeling workflow.

## Scope

Use this project when the task involves one or more of the following:

- Building or revising an ASM model from a task file and spreadsheet input
- Inspecting intermediate ASM artifacts
- Adjusting workflow logic, config extraction, calibration, or report generation
- Analyzing sensitivity, calibration, figure output, or final results

## Input contract

A typical task provides three kinds of inputs:

1. A task markdown file under `task/`
2. A spreadsheet under `input/`
3. Optional process notes, field definitions, or output conventions

If the task names a specific data file, target variable, boundary condition, or calibration rule, treat that as the primary source of truth.

## Read order

Do not load every reference at once. Read only what is needed for the current stage.

Stage references:

- `references/knowledge-agent.md`
- `references/plan-agent.md`
- `references/modeling-agent.md`
- `references/reflection-agent.md`
- `references/artifact-schema.md`
- `references/task-writing.md` only when creating or revising a task file

Basic rule:

- Understand the task first
- Then write the plan
- Then extract the config
- Then validate it
- Then run the model
- Then summarize the run

## End-to-end workflow

1. Read the task, the data preview, and the process guide.
2. Generate `midoutput/WWTPProcessContext.md`.
3. Generate `midoutput/asm_plan.md`.
4. Extract `midoutput/asm_config_before.json`.
5. Finalize `midoutput/asm_config_after.json` and `midoutput/asm_config.json`.
6. Validate the config and repair it if needed.
7. Run sensitivity analysis and parameter calibration.
8. Generate reports, figures, traces, and final summaries.

## Stage 1: Understand the task

The first goal is to identify:

- What process is being modeled
- Whether the task is a single tank, a subsystem, or a more complete process
- What pollutants or states are targets
- Which boundary conditions must be considered
- Which spreadsheet file should be used

Use explicit task wording as a modeling constraint. For example, phrases such as:

- simplified nitrogen removal
- EBPR
- N2O
- return sludge
- chemical dosing

should be treated as structural model clues, not decorative notes.

If the task and the spreadsheet disagree, keep the task requirements explicit and explain the actual meaning of the visible columns in the process context.

## Stage 2: Generate process context

Output:

- `midoutput/WWTPProcessContext.md`

Requirements:

- Only describe process decisions supported by the task and visible data
- Only interpret columns that actually exist in the spreadsheet
- Avoid generic background, history, or policy discussion
- Keep it short, factual, and usable for the next stage

If the data file is missing, unreadable, or the process direction cannot be established, record the issue as a failure instead of inventing a conclusion.

## Stage 3: Generate the ASM plan

Output:

- `midoutput/asm_plan.md`

Requirements:

- Markdown prose only
- Preserve the original task text
- State the chosen model complexity, calibration mode, targets, sensitivity settings, iteration budget, and boundary terms
- The plan must be executable in intent, not abstract

The plan should answer:

- Which `modelcomplex` is selected
- Which `calibmode` is selected
- Which variables belong in `sens_targets`
- Which file is used as `xlsx_path`
- What values are used for `sens_delta`, `senstopk`, and `maxiter`
- Which boundary terms are enabled, and which are disabled

If the plan conflicts with the task, fix the plan before moving forward.

## Stage 4: Extract configuration

Output:

- `midoutput/asm_config_before.json`

Requirements:

- Keep only the 8 required top-level fields
- Ensure `boundaries` has exactly 6 fixed keys
- Do not emit extra fields
- Keep `sens_targets` as a variable-name-to-weight dictionary

Required top-level fields:

- `modelcomplex`
- `calibmode`
- `sens_targets`
- `xlsx_path`
- `sens_delta`
- `senstopk`
- `maxiter`
- `boundaries`

If the plan cannot be converted into valid JSON, return the problem to the previous stage and fix the plan first.

## Stage 5: Finalize config and parameters

Outputs:

- `midoutput/asm_config_after.json`
- `midoutput/asm_config.json`

Requirements:

- Preserve the logic of `asm_config_before.json`
- Add the model-specific parameter subset
- Ensure the final config is runnable

If parameters are missing, names are invalid, boundary shapes are wrong, paths escape the project, or targets do not belong to the active model, repair the config before continuing.

## Stage 6: Validate and reflect

Validation should check:

- Required fields are present
- `modelcomplex` is allowed
- `calibmode` is allowed
- `sens_targets` uses only active variables
- `sens_targets` count matches the calibration mode
- `xlsx_path` exists and ends with `.xlsx`
- Numeric fields are in range
- `boundaries` contains the 6 fixed keys
- `params` is a non-empty, model-specific parameter subset

If validation fails:

1. Record the exact issue
2. Send the issue back to the modeling stage
3. Re-extract or repair the config
4. Validate again

Do not send a questionable config into model execution.

## Stage 7: Run the model

Before running, make sure:

- `midoutput/model.py` exists
- `midoutput/asm_config.json` exists
- The input spreadsheet is readable
- The output directory is writable

After a successful run, expect files such as:

- `midoutput/param_ori.json`
- `midoutput/param_ref.json`
- `midoutput/param_opt.json`
- `midoutput/sensitivity.json`
- `midoutput/calibration.json`
- plots under `figs/`

If model execution fails, preserve the return code and error output instead of hiding the exception.

## Stage 8: Summarize the run

Final outputs should include:

- `asm_report.md`
- `asm_report.pdf`
- `final_result.json`
- `execution_trace.json`
- `process_checks.json`

`final_result.json` should summarize:

- Run status
- Failure reason, if any
- Final config path
- Main artifact paths
- Parameter change information
- Key fit metrics

`execution_trace.json` should record:

- Run directory
- Command executed
- Return code
- Runtime duration
- Standard output and standard error summary

`process_checks.json` should record:

- Whether required files exist
- Whether the directory structure is correct
- Whether unnecessary temporary scripts remain
- Whether the task-level outputs are complete

## Failure and return logic

If a stage cannot proceed, return to the closest stage that can still be fixed:

- Wrong process understanding -> return to Stage 1 or 2
- Wrong planning decision -> return to Stage 3
- Invalid JSON structure -> return to Stage 4
- Wrong model scope, boundaries, or parameter subset -> return to Stage 5
- Validation failure -> return to Stage 4 or 5
- Model execution failure with a valid config -> inspect `scripts/`

Typical failure cases:

- Missing input file
- Missing data columns
- Plan cannot be turned into valid JSON
- Targets are not active for the selected model
- Boundary fields are incomplete
- Path escapes the project directory
- Numeric ranges are invalid
- Numerical solver failure

Handling rule:

- Locate the exact file first
- Fix deterministic code when possible
- Report the problem clearly when it cannot be fixed
- Never hide an error silently

## Output layout

Keep each run isolated under `output/task-*/` with this structure:

- `midoutput/` for intermediate markdown, JSON, and runnable model files
- `figs/` for plots and figure data
- run-level report and trace files in the task directory

Keep filenames stable so downstream checks can locate them.

## Working rules

- Treat `scripts/` as the execution and reporting layer
- Treat `references/` as the rule and explanation layer
- Do not mix files across tasks
- Do not reuse old outputs as the input to a new task
- When behavior is unstable, prefer deterministic script fixes
- Do not create root-level `.py` files
- Do not leave unnecessary cache directories or temporary files

## What this project covers

- Task intake and process identification
- ASM plan generation
- Config extraction and finalization
- Reflection-based validation and repair
- Sensitivity analysis and calibration
- Report, figure, and trace generation
- Execution script and output structure management

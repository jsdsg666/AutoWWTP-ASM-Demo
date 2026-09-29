# Architecture

The skill bundles the AutoWWTP-ASM modeling stack.

## Main layers

- `scripts/asmlibrary.py`: model definitions, simulation, sensitivity analysis, calibration, and plotting
- `scripts/asmmodel.py`: runnable entry point that loads `asm_config.json` and writes report artifacts
- `scripts/config_finalize.py`: config shaping and parameter projection helpers
- `scripts/report_template.py`: report assembly
- `scripts/Vtolatex.py`: notation conversion utilities
- `scripts/param.json`: default parameter set
- `scripts/param_meaning.md`: parameter semantics
- `references/WWTPProcessGuide.md`: process knowledge

## Workflow role

The workflow is:

task text -> process understanding -> ASM plan -> JSON config -> pipeline run -> calibration/report artifacts

Keep the layers separate. Do not mix prompt-writing concerns with numerical modeling code.

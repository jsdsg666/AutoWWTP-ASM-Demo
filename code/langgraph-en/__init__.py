"""langgraph-en - LangGraph multi-agent ASM mechanistic modeling pipeline.

Workflow:
  START -> prepare_environment -> knowledge_agent
        -> plan_agent -> human_confirm
        -> modeling_agent (asm_plan.md -> asm_config.json)
        -> reflection_agent (static validation + LLM semantic comparison)
        -> run_model (subprocess runs midoutput/model.py)
        -> report_summary -> END

Core traits:
  - Modeling kernel: script/asmlibrary.py, with run_pipeline(...) as the only entry point.
  - plan_agent carries modelcomplex, calibmode, and sens_targets decisions.
  - modeling_agent extracts the 8-field asm_config.json from asm_plan.md.
  - reflection_agent decides config_ok through Python validation and LLM semantic comparison.
  - run_model writes asm_report.md and asm_report.pdf.
"""


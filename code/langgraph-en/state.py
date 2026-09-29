"""Shared LangGraph StateGraph state definition for the asmlibrary.run_pipeline workflow.

Each node receives the current state and returns partial field updates.
plan_agent produces asm_plan.md; modeling_agent extracts asm_config.json; reflection_agent
validates it; run_model executes midoutput/model.py after approval.
"""
from __future__ import annotations

from typing import TypedDict


class AgentState(TypedDict, total=False):
    # User input
    user_task: str

    # KnowledgeAgent artifact
    process_context_md: str   # midoutput/WWTPProcessContext.md content

    # PlanAgent artifact
    asm_plan_md: str          # midoutput/asm_plan.md content

    # ModelingAgent artifacts
    asm_config_before: dict   # midoutput/asm_config_before.json content
    asm_config: dict          # midoutput/asm_config.json content after finalization

    # run_model subprocess result
    last_stdout: str
    last_stderr: str
    last_returncode: int
    ode_solver_success: bool

    # reflection_agent validation result
    config_ok: bool                    # True routes to run_model; False routes back to modeling_agent
    reflection_retry_count: int        # regeneration count
    reflection_issues: list            # validation issues used by modeling_agent for regeneration

    # Global
    status: str               # ok / failed / pending / aborted
    log: list[str]            # scheduler log
    fatal_error: str          # termination reason

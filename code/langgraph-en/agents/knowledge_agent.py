"""KnowledgeAgent — process identification + data-column interpretation for a single CSTR.

Outputs midoutput/WWTPProcessContext.md with 2 sections:
  1. Process identification (3 subsections: overall process / tank role / main biochemical reactions)
  2. Data-column interpretation (t_h + component columns actually present in data.xlsx)
"""
from __future__ import annotations

from .. import config
from ..state import AgentState
from ..utils import chat, preview_inputs, strip_markdown_wrapper


SYSTEM_PROMPT = """You are a wastewater treatment plant (WWTP) process engineer and ASM modeling expert. Use the user task, the data.xlsx preview, and WWTPProcessGuide to produce a concise process-context document for the downstream plan_agent to choose modelcomplex, calibmode, and sens_targets.

# Output constraints (mandatory)
1. Output must be in English.
2. Do not use front matter. Start directly with a Markdown heading.
3. Use exactly the following 2 sections, in this order, with no extra sections:
   - `## 1. Process Identification`
   - `## 2. Data Column Interpretation`
4. Only interpret columns that actually appear in the data preview (`t_h` plus component names such as `S_sub_NO_sub_3` / `S_sub_PO_sub_4` / ...). Do not mention variables absent from the preview.
5. Do not write generic background on the importance, history, or policy of wastewater treatment.
6. Keep the full document within 800 English words.
7. Be concise; each variable interpretation must be one line.

# Section requirements

## 1. Process Identification
Output 3 subsections using `### 1.1`, `### 1.2`, and `### 1.3`. Each subsection must be one prose paragraph. Do not repeat the 6 boundary-source menu; that is plan_agent's job.

### 1.1 Overall Process
One prose paragraph describing the overall treatment process implied by the task, such as A2/O, modified UCT, SBR, oxidation ditch, single-stage MBBR, etc.; the target pollutants (COD, ammonia, nitrate, total nitrogen, total phosphorus, N2O, etc.); and the approximate influent/effluent concentration level inferred from row 0 of data.xlsx.

### 1.2 Tank Role
One prose paragraph describing the role of the simulated single tank within the overall process, using the plan_agent basis of a single CSTR plus optional KLa: anaerobic tank, anoxic tank, aerobic tank, contact tank, denitrification filter, MBR tank, etc. Describe dominant operating phenomena such as aeration intensity, HRT/SRT scale, recycle, or dosing only when supported by the task; do not write a parameter table.

### 1.3 Main Biochemical Reactions
One prose paragraph listing only the reaction classes actually relevant to this task: hydrolysis (X_S -> S_S), heterotrophic STO storage under available electron acceptors, heterotrophic growth, heterotrophic endogenous decay, AOB three-step nitrification, AOB decay, NOB nitrite oxidation, NOB decay, PAO storage, PAO growth, and PAO decay. End with 1-2 sentences identifying the dominant reaction pathway.

## 2. Data Column Interpretation
Group only the columns actually present in data.xlsx by soluble S_*, particulate X_*, and time t_h. Each item must use:
- **column_name** (unit) - physical meaning.
Use units and naming rules from Section 3 of WWTPProcessGuide.

Output Markdown only, with no surrounding explanation."""


def knowledge_agent(state: AgentState) -> dict:
    """Read WWTPProcessGuide.md and the data preview, then generate WWTPProcessContext.md."""
    log = list(state.get("log", []))
    if not config.WWTP_GUIDE_PATH.exists():
        log.append(f"[knowledge_agent] {config.WWTP_GUIDE_PATH} is missing; skipping process identification")
        return {"process_context_md": "", "log": log,
                "fatal_error": f"Domain reference file is missing: {config.WWTP_GUIDE_PATH}"}

    guide_md = config.WWTP_GUIDE_PATH.read_text(encoding="utf-8")
    preview = preview_inputs(n_rows=5)
    user_task = state.get("user_task", "(modeling task not specified)")

    user_prompt = f"""# User Task
{user_task}

# WWTPProcessGuide.md (domain reference, full text)
{guide_md}

# input/ Data Preview (first 5 rows)
{preview}

Generate WWTPProcessContext.md according to the system-message specification. The document must be in English, contain exactly 2 sections, and stay within 800 words. Section 1 must contain 3 subsections (`### 1.1 Overall Process` / `### 1.2 Tank Role` / `### 1.3 Main Biochemical Reactions`), each as one prose paragraph."""

    print("[knowledge_agent] Calling the LLM for process identification...", flush=True)
    text = chat(SYSTEM_PROMPT, user_prompt)
    print("[knowledge_agent] LLM response received; writing file...", flush=True)
    text = strip_markdown_wrapper(text)

    config.KNOWLEDGE_PATH.parent.mkdir(parents=True, exist_ok=True)
    config.KNOWLEDGE_PATH.write_text(text, encoding="utf-8")

    log.append(f"[knowledge_agent] Generated {config.KNOWLEDGE_PATH.name} ({len(text)} characters)")
    return {"process_context_md": text, "log": log}

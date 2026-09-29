# AutoWWTP-ASM Open Code Bundle

This directory contains the open-code bundle for AutoWWTP-ASM, and project-style packages for Codex and Claude Code.

AutoWWTP-ASM is designed for ASM modeling tasks in wastewater treatment plants. Given a task description and input data, it identifies the process context, generates an ASM modeling plan, extracts executable model configuration, runs sensitivity analysis and parameter calibration, and produces reports, figures, traces, and final results.

<!-- Example video: example.mp4 (AutoWWTP-ASM workflow demonstration) -->

## Directory Layout

- `code/`: source projects and comparison variants
- `data/`: open data or reorganized data files
- `task/`: open task descriptions
- `example output/`: example output results
- `failure test example/`: failed-case result summaries; only JSON files that did not pass process checks are retained
- `LICENSE`: MIT license
- `readme-cn.md`: Chinese documentation
- `readme-en.md`: English documentation

## Projects in `code/`

- `langgraph-en`: main project with the full LangGraph multi-agent workflow
- `skill`: AutoWWTP-ASM packaged as a Codex skill
- `autowwtp-asm-codex`: Codex project structure with `AGENTS.md` and `.codex/agents/*.toml`
- `autowwtp-asm-claude`: Claude Code project structure with `CLAUDE.md` and `.claude/agents/*.md`

## Main Project: `langgraph-en`

Main project path:

```text
F:\wyq\lunwen\lunwen24_AutoWWTP-asm\code\code\open\allopen\code\langgraph-en
```

Core files and folders:

- `main.py`: command-line entry point
- `coordinator_agent.py`: multi-agent coordinator
- `agents/knowledge_agent.py`: generates the process and data context
- `agents/plan_agent.py`: generates the ASM modeling plan
- `agents/modeling_agent.py`: extracts executable configuration from the plan
- `agents/reflection_agent.py`: checks and repairs the configuration
- `script/asmlibrary.py`: core ASM modeling, sensitivity analysis, and calibration library
- `script/asmmodel.py`: model execution template
- `script/config_finalize.py`: configuration completion and parameter consolidation
- `script/report_template.py`: report-generation template
- `references/WWTPProcessGuide.md`: reference for wastewater process and variable interpretation
- `input/`: input spreadsheets
- `task/`: task descriptions

## Workflow

The default `langgraph-en` workflow is:

1. Read the task description and input data.
2. `knowledge_agent` generates `WWTPProcessContext.md`.
3. `plan_agent` generates `asm_plan.md`.
4. `modeling_agent` generates `asm_config_before.json`.
5. `config_finalize.py` completes parameters and generates `asm_config_after.json` and `asm_config.json`.
6. `reflection_agent` checks model scope, target variables, boundary conditions, and parameter settings.
7. `asmmodel.py` calls `asmlibrary.py` to run sensitivity analysis and parameter calibration.
8. Generate reports, figures, execution traces, and the final result summary.

## Environment Setup

Python 3.10 or later is recommended.

Common dependencies:

```bash
pip install langgraph langchain-core langchain-openai langchain-anthropic langchain-google-genai pandas numpy scipy matplotlib openpyxl markdown-pdf pymoo
```

Dependency roles:

- `langgraph`: multi-agent workflow orchestration
- `langchain-*`: connection to different LLM providers
- `pandas/openpyxl`: Excel data loading
- `numpy/scipy/matplotlib`: numerical solving, calibration, and plotting
- `markdown-pdf`: PDF report export
- `pymoo`: Pareto/NSGA-II multi-objective calibration

## LLM Configuration

Configure the model service through environment variables before running. Do not write real API keys into source code.

PowerShell example:

```powershell
$env:AUTOWWTP_LLM_API_KEY="your-api-key"
$env:AUTOWWTP_LLM_BASE_URL="https://api.example.com/v1"
$env:AUTOWWTP_LLM_MODEL="your-model-name"
$env:AUTOWWTP_LLM_MESSAGE_CLASS="openai"
$env:AUTOWWTP_LLM_TEMPERATURE="1.0"
```

Typical values for `AUTOWWTP_LLM_MESSAGE_CLASS` include:

- `openai`
- `anthropic`
- `gemini`

## How to Run

Enter the main project directory:

```powershell
cd F:\wyq\lunwen\lunwen24_AutoWWTP-asm\code\code\open\allopen\code\langgraph-en
```

### Option 1: Run with a task file

```powershell
python main.py --task-file task/task1.md
```

### Option 2: Pass the task text directly

```powershell
python main.py --task "Modeling using autowwtp-asm. Data are located at input/data1.xlsx. Build an ASM model ..."
```

### Option 3: Interactive single-task mode

```powershell
python main.py --once
```

After startup, paste the task description and finish with an empty line.

### Option 4: Chat-trigger mode

```powershell
python main.py
```

In the interactive session, include the trigger word `autowwtp-asm` followed by the modeling task.

### Option 5: Human-in-the-loop plan review

```powershell
python main.py --task-file task/task1.md --hitl-plan
```

This mode pauses after `asm_plan.md` is generated, allowing manual inspection or editing before execution continues.

## Output Files

Each run creates a new task directory under the main project:

```text
output/task-YYYYMMDD-HHMMSS-ffffff/
```

Typical outputs include:

- `midoutput/WWTPProcessContext.md`
- `midoutput/asm_plan.md`
- `midoutput/asm_config_before.json`
- `midoutput/asm_config_after.json`
- `midoutput/asm_config.json`
- `midoutput/sensitivity.json`
- `midoutput/calibration.json`
- `figs/`
- `asm_report.md`
- `asm_report.pdf`
- `final_result.json`
- `execution_trace.json`
- `process_checks.json`

## Tasks and Data

Task files are located in:

```text
code/langgraph-en/task/
```

Input data are located in:

```text
code/langgraph-en/input/
```

The task description should clearly specify:

- data file path, such as `input/data1.xlsx`
- modeled object, such as anaerobic tank, anoxic tank, aerobic tank, or the full process section
- target pollutants or state variables
- whether boundary conditions are considered, such as return flow, aeration, dosing, or external carbon source
- calibration targets and expected outputs

## License

This code bundle is released under the MIT License. See the formal license text in:

```text
LICENSE
```

Some personal thoughts from the first author, Yu-Qi Wang:
This is my first research paper on Agents, and it may also be the first study on long-horizon Agents published in EST. If you have read the paper and arrived here, I believe you are also a hardworking researcher.
This study was completed in 2025, submitted in 2026, and accepted in September 2026. During this process, I experienced the generational evolution of GPT from version 3 to version 6, while the research framework, methods, and LLMs used in the study were revised repeatedly. I believe you have already read about many of the strengths of this work in the paper. However, AI is developing so rapidly that it is difficult to know whether these methods will remain sufficiently innovative several years from now. Therefore, I would like to discuss some limitations here:
1. This study constrains the inputs and outputs of the LLM through a relatively fixed, predefined model library. Although this approach greatly reduces hallucinations, it also limits the model’s autonomy. As LLM capabilities continue to improve and Agent frameworks evolve, could models generate code directly in the future? Examples include the latest Claude Fable 5.1 and GPT-6, as well as the Cordis framework behind DeepSeek Harness.
2. Could the benchmark include more wastewater treatment scenarios and corresponding tasks?
3. Scenario-specific metrics are difficult to identify, and the reproducibility of LLM-as-a-judge remains relatively limited. This type of research still requires substantial human involvement.
Because I have been awarded a new project, I am unable to continue developing this project. There are still many practical ideas that could be pursued along this research path, and I welcome everyone to contact me at 17877784587@163.com. I also hope that you will share your suggestions.
Finally, I would like to thank my handling editor and the three reviewers for their valuable suggestions during the EST submission process. I do not know whether you will return to look at this work, but your suggestions truly helped me. LLM Agents remain an emerging research direction in the environmental field. I am grateful to these rigorous and kind editors and reviewers.

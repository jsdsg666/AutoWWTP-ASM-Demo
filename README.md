# AutoWWTP-ASM

[中文](#中文) | [English](#english)

🎬 [点击打开示例视频（example.mp4）](https://github.com/jsdsg666/AutoWWTP-ASM-Demo/blob/main/example.mp4)

---

## 中文

# AutoWWTP-ASM 开源代码包

本目录是 AutoWWTP-ASM 的开源整理版本，包含完整多智能体建模流程、消融实验版本、单智能体对比版本，以及面向 Codex 和 Claude Code 的项目化封装。

AutoWWTP-ASM 面向污水处理厂 ASM 建模任务：根据任务文本和输入数据，自动识别工艺背景，生成 ASM 建模计划，抽取可运行配置，执行敏感性分析与参数校准，并生成报告、图件和追踪结果。

<!-- 示例视频：example.mp4（AutoWWTP-ASM 使用流程演示） -->

## 目录结构

- `code/`：各类源码项目和对比版本
- `data/`：开放数据或整理后的数据文件
- `task/`：开放任务说明
- `example output/`：示例输出结果
- `failure test example/`：失败案例结果摘要，仅保留未通过过程检查的 JSON 文件
- `LICENSE`：MIT 开源协议
- `readme-cn.md`：中文说明
- `readme-en.md`：英文说明

## `code/` 下的项目

- `langgraph-en`：主项目，完整 LangGraph 多智能体工作流
- `langgraph-en-no-knowledge`：去掉 knowledge 阶段的消融版本
- `langgraph-en-no-plan`：去掉 plan 阶段的消融版本
- `langgraph-en-no-reflection`：去掉 reflection 阶段的消融版本
- `langgraph-en-sa`：单智能体对比版本
- `langgraph-en-sa-f`：带额外自检逻辑的单智能体对比版本
- `skill`：封装为 Codex skill 的版本
- `autowwtp-asm-codex`：按 Codex 项目结构组织的版本，包含 `AGENTS.md` 和 `.codex/agents/*.toml`
- `autowwtp-asm-claude`：按 Claude Code 项目结构组织的版本，包含 `CLAUDE.md` 和 `.claude/agents/*.md`

## 主项目：`langgraph-en`

主项目路径：

```text
F:\wyq\lunwen\lunwen24_AutoWWTP-asm\code\code\open\allopen\code\langgraph-en
```

核心结构：

- `main.py`：命令行入口
- `coordinator_agent.py`：多智能体调度器
- `agents/knowledge_agent.py`：生成工艺与数据上下文
- `agents/plan_agent.py`：生成 ASM 建模计划
- `agents/modeling_agent.py`：从计划中抽取可运行配置
- `agents/reflection_agent.py`：检查和修复配置
- `script/asmlibrary.py`：ASM 模型、敏感性分析和校准核心
- `script/asmmodel.py`：模型执行模板
- `script/config_finalize.py`：配置补全和参数整理
- `script/report_template.py`：报告生成模板
- `references/WWTPProcessGuide.md`：污水处理与变量说明参考
- `input/`：输入数据表
- `task/`：任务文本

## 工作流

`langgraph-en` 的默认流程如下：

1. 读取任务文本和输入数据。
2. `knowledge_agent` 生成 `WWTPProcessContext.md`。
3. `plan_agent` 生成 `asm_plan.md`。
4. `modeling_agent` 生成 `asm_config_before.json`。
5. `config_finalize.py` 补全参数并生成 `asm_config_after.json` 和 `asm_config.json`。
6. `reflection_agent` 检查模型范围、目标变量、边界条件和参数配置。
7. `asmmodel.py` 调用 `asmlibrary.py` 执行敏感性分析和参数校准。
8. 生成报告、图件、运行追踪和最终结果摘要。

## 环境准备

建议使用 Python 3.10 或更高版本。

常用依赖包括：

```bash
pip install langgraph langchain-core langchain-openai langchain-anthropic langchain-google-genai pandas numpy scipy matplotlib openpyxl markdown-pdf pymoo
```

其中：

- `langgraph` 用于多智能体流程调度
- `langchain-*` 用于连接不同 LLM 服务
- `pandas/openpyxl` 用于读取 Excel 数据
- `numpy/scipy/matplotlib` 用于数值求解、校准和绘图
- `markdown-pdf` 用于导出 PDF 报告
- `pymoo` 用于 Pareto/NSGA-II 多目标校准

## LLM 配置

运行前建议通过环境变量配置模型服务，不要把真实密钥写入代码。

PowerShell 示例：

```powershell
$env:AUTOWWTP_LLM_API_KEY="your-api-key"
$env:AUTOWWTP_LLM_BASE_URL="https://api.example.com/v1"
$env:AUTOWWTP_LLM_MODEL="your-model-name"
$env:AUTOWWTP_LLM_MESSAGE_CLASS="openai"
```

可用的 `AUTOWWTP_LLM_MESSAGE_CLASS` 通常包括：

- `openai`
- `anthropic`
- `gemini`

## 启动方式

进入主项目目录：

```powershell
cd F:\wyq\lunwen\lunwen24_AutoWWTP-asm\code\code\open\allopen\code\langgraph-en
```

### 方式 1：使用任务文件运行

```powershell
python main.py --task-file task/task1.md
```

### 方式 2：直接传入任务文本

```powershell
python main.py --task "Modeling using autowwtp-asm. Data are located at input/data1.xlsx. Build an ASM model ..."
```

### 方式 3：交互式单任务模式

```powershell
python main.py --once
```

启动后粘贴任务说明，输入空行结束。

### 方式 4：聊天触发模式

```powershell
python main.py
```

进入交互后，在消息中包含触发词 `autowwtp-asm`，后面接具体建模任务。

### 方式 5：人工确认计划

```powershell
python main.py --task-file task/task1.md --hitl-plan
```

该模式会在生成 `asm_plan.md` 后暂停，允许人工检查或修改计划，再继续执行。

## 输出文件

每次运行会在主项目下生成新的任务目录：

```text
output/task-YYYYMMDD-HHMMSS-ffffff/
```

典型输出包括：

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

## 任务与数据

任务文件位于：

```text
code/langgraph-en/task/
```

输入数据位于：

```text
code/langgraph-en/input/
```

任务文本中应明确写出：

- 数据文件路径，例如 `input/data1.xlsx`
- 模拟对象，例如厌氧池、缺氧池、好氧池或完整工艺段
- 目标污染物或状态变量
- 是否考虑边界条件，例如回流、曝气、加药、外碳源等
- 校准目标和期望输出

## 失败案例结果

`failure test example/` 保留了 13 个未通过过程检查的结果摘要。每个文件均为有效 JSON，且其 `process_checks_passed` 字段为 `false`。

## 其他版本说明

消融版本用于验证不同模块对最终建模表现的贡献：

- `langgraph-en-no-knowledge`：测试没有工艺识别阶段时的影响
- `langgraph-en-no-plan`：测试没有显式计划阶段时的影响
- `langgraph-en-no-reflection`：测试没有配置反思校验时的影响

单智能体版本用于和多智能体工作流对比：

- `langgraph-en-sa`
- `langgraph-en-sa-f`

项目化封装版本用于比较不同 agent 平台的组织方式：

- `autowwtp-asm-codex`
- `autowwtp-asm-claude`
- `skill`

## 开源协议

本代码包采用 MIT License。正式许可文本见：

```text
LICENSE
```


---

## English

# AutoWWTP-ASM Open Code Bundle

This directory contains the open-code bundle for AutoWWTP-ASM, including the full multi-agent modeling workflow, ablation variants, single-agent comparison variants, and project-style packages for Codex and Claude Code.

AutoWWTP-ASM is designed for ASM modeling tasks in wastewater treatment plants. Given a task description and input data, it identifies the process context, generates an ASM modeling plan, extracts executable model configuration, runs sensitivity analysis and parameter calibration, and produces reports, figures, traces, and final results.

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
- `langgraph-en-no-knowledge`: ablation version without the knowledge stage
- `langgraph-en-no-plan`: ablation version without the planning stage
- `langgraph-en-no-reflection`: ablation version without the reflection stage
- `langgraph-en-sa`: single-agent comparison version
- `langgraph-en-sa-f`: single-agent comparison version with additional self-check logic
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

## Failed-Case Results

`failure test example/` retains 13 result summaries that did not pass the process checks. Each file is valid JSON with `process_checks_passed` set to `false`.

## Other Variants

Ablation variants are used to evaluate the contribution of different modules:

- `langgraph-en-no-knowledge`: tests the effect of removing the process-identification stage
- `langgraph-en-no-plan`: tests the effect of removing the explicit planning stage
- `langgraph-en-no-reflection`: tests the effect of removing configuration reflection and checking

Single-agent variants are used for comparison with the multi-agent workflow:

- `langgraph-en-sa`
- `langgraph-en-sa-f`

Project-packaged variants are used to compare organization patterns across agent platforms:

- `autowwtp-asm-codex`
- `autowwtp-asm-claude`
- `skill`

## License

This code bundle is released under the MIT License. See the formal license text in:

```text
LICENSE
```

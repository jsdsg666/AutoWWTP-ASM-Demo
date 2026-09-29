# AutoWWTP-ASM 开源代码包

本目录是 AutoWWTP-ASM 的开源整理版本，以及面向 Codex 和 Claude Code 的项目化封装。

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

## 开源协议

本代码包采用 MIT License。正式许可文本见：

```text
LICENSE
```

第一作者王煜琪 / Yu-Qi Wang的一些心里话：
这是我的第一篇 Agent 研究论文，也可能是 EST 上第一篇针对长流程 Agent 的研究论文。如果您读过这篇文章并来到这里，相信您也是一位努力工作的研究者。
这项研究于 2025 年完成，2026 年投稿，并于 2026 年 9 月接收。在此过程中，我经历了 GPT 从 3 到 6 的跨代升级，研究框架、方法和所使用的 LLM 也反复调整。相信您已经在论文中了解了本研究的许多优点。AI 发展得太快，很难判断几年后这些方法是否仍然足够创新。因此，我更希望在这里讨论一些研究局限：
1. 本研究通过相对固定的预设模型库限制 LLM 的输入和输出。这种方法在大幅降低幻觉的同时，也降低了模型的自主性。随着 LLM 能力提升以及 Agent 框架约束方式的发展，未来是否可以让模型直接生成代码？例如最新的 Claude Fable 5.1、GPT-6，以及 DeepSeek Harness 背后的 Cordis 框架。
2. Benchmark 部分是否可以加入更多污水处理场景，并设计相应的任务？
3. 场景专用指标很难寻找，而 LLM-as-a-judge 的可复现性相对较差。这类工作仍然非常需要人工参与。
由于我申请到了新的项目，无法继续推进当前项目。这条研究路径上仍然有许多可以落地的想法，欢迎大家与我联系：17877784587@163.com。也希望大家能够提出宝贵建议。
最后，感谢我在 EST 投稿期间的主编和三位审稿人所提供的宝贵意见。我不知道你们是否会再次回来看这项研究，但你们的建议确实给了我很大帮助。LLM Agent 在环境领域仍然是一个新兴方向，感谢这些严格而友善的编辑和审稿人。

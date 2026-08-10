# AutoWWTP-ASM Open Code Bundle

[中文](#中文) | [English](#english)

## 中文

AutoWWTP-ASM 是一个面向污水处理厂活性污泥模型（ASM）建模的多智能体代码包。它可根据任务文本和输入数据识别工艺背景、生成建模计划、提取可执行配置、执行敏感性分析和参数校准，并输出报告、图件与运行追踪结果。

本仓库包括：

- 完整的 LangGraph 多智能体工作流及消融实验版本
- 单智能体对比版本
- 面向 Codex 和 Claude Code 的项目化封装
- 开放数据、任务描述、示例输出和压力测试文件

完整中文使用说明请见 [readme-cn.md](readme-cn.md)。

## English

AutoWWTP-ASM is a multi-agent code bundle for activated sludge model (ASM) modeling in wastewater treatment plants. Given a task description and input data, it identifies the process context, creates a modeling plan, extracts executable configuration, runs sensitivity analysis and parameter calibration, and produces reports, figures, and execution traces.

This repository includes:

- The full LangGraph multi-agent workflow and ablation variants
- Single-agent comparison variants
- Project packages for Codex and Claude Code
- Open data, task descriptions, example outputs, and stress-test files

For the full English guide, see [readme-en.md](readme-en.md).

## License

Released under the [MIT License](LICENSE).

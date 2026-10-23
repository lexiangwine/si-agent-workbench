# SI-WB-001 初始化可运行的 SI Agent Workbench

## Goal
把空仓库搭成可在 VS Code 使用的任务与交付工作台，整合现有 SI-QA 工程规范和声画科技交付阶段门禁。

## Owner and scope
实现负责人：Codex。人工复核负责人：仓库所有者。
允许修改：本任务所需的 workbench、workflows、agents、config、examples、tests、scripts、docs、README、.vscode、CI 和仓库配置。
禁止：客户真实资料、密钥、生产部署、自动合并；不修改任何已有受保护 CI 设置。本次仅初始化空仓库的新 CI。

## Definition of Done
- 提供零第三方运行依赖的 Python CLI、本地只读看板、VS Code 任务。
- 支持工程协作和系统集成项目交付两条流程。
- 支持离线演示、手动导入、多供应商 HTTP 接口；线上调用必须明确允许，未配置模型不能调用。
- 项目资料和密钥默认不进入 Git；阶段审批绑定输入和输出版本，发生变更时失效。
- 测试覆盖审批、异常、并发写锁、路径、网络边界、协议与端到端操作。
- 提供快速启动、选型边界、任务规则、上线与回退文档。
- 提交关联 Issue 的 PR，报告真实检查结果，等待人工审核。

## Evidence
由 docs/VALIDATION.md 记录本地验证；GitHub PR 提供最终 CI 结果。

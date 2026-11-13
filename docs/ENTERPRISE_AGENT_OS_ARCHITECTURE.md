# SI Agent Workbench：企业级智能体操作系统目标架构

- 文档类型：Target Architecture / Architecture Reference
- 状态：Proposed（目标架构基线；分阶段实施）
- 版本：1.0
- 适用范围：SI Agent Workbench 当前多 Agent 协作工作台及后续企业级演进
- 上游参考：用户提供的《AI Agent Platform Architecture — Educational Reference Architecture》架构图（2026-11-14 纳入）

## 1. 架构决策摘要

将参考图纳入 SI Agent Workbench 总体架构，作为从多 Agent 协作工作台演进为企业级智能体操作系统的目标架构依据。该图是能力参考，不是当前实现清单，也不意味着立即引入图中所有技术栈。

架构演进必须遵守以下原则：

1. **先交付业务闭环，再扩展平台能力**：每个模块必须对应真实场景、验收标准和可量化收益。
2. **控制平面与执行平面分离**：编排、策略、审批和审计负责决策治理；模型、工具和沙箱负责受控执行。
3. **模型与工具可插拔**：通过稳定接口接入不同模型供应商、Agent Runtime 和 MCP Server，避免绑定单一厂商。
4. **默认最小权限**：工具按身份、项目、任务和动作授权；读取、写入、外发、删除、部署分级。
5. **高风险动作 Human-in-the-Loop**：审批绑定具体任务、输入版本、目标资源和动作参数；任何关键输入变化都要求重新审批。
6. **执行结果必须可验证**：输出不能仅凭 Agent 自述通过；需要测试、证据、独立审查和验收记录。
7. **可观测、可恢复、可审计**：记录任务状态、模型与工具调用、成本用量、策略判定、审批和结果摘要。
8. **渐进式复杂度**：V1 保持本地优先、轻依赖；只有出现跨机器协作、并发、可靠性或合规需求时才引入相应基础设施。

## 2. 总体架构分层

### 2.1 接入层（Access Layer）

- 用户入口：VS Code、CLI、本地 Web Dashboard；后续可扩展 Chat、Slack、API。
- Agent Gateway：统一身份识别、请求校验、会话关联、限流和请求路由。
- Identity & Auth：用户、团队、服务身份；SSO/OAuth、角色与项目范围授权。

当前状态：本地 CLI、只读 Dashboard 和人工驱动的 VS Code Agent 交接已具备；云端账号、租户和 SSO 未实现。

### 2.2 控制平面（Control Plane）

- Agent Registry：Agent 定义、角色提示词、工具授权、模型偏好、版本和生命周期。
- Agent Orchestrator：任务拆解、依赖编排、子 Agent 委派、状态机、重试策略、超时与恢复。
- LLM Router：按任务类型、质量要求、延迟、预算和供应商健康度选择模型；支持 fallback 和路由审计。
- Context & Memory Service：会话上下文、项目记忆、用户偏好、知识检索；记忆需有来源、权限、时效和删除策略。
- Policy / Permission Engine：执行前策略判定，落实最小权限和读写分级。
- Approval Queue：暂停高风险动作，执行人工批准、拒绝、超时和升级流程。

当前状态：已有阶段式 Engine、角色配置、模型 Provider 路由、版本绑定审批和变更失效机制；独立注册中心、动态策略服务、长期记忆和在线审批队列尚未实现。

### 2.3 执行平面（Execution Plane）

- Agent Runtime：运行规划、执行、研究、开发、审查等专业 Agent。
- Tool Registry：工具 Schema、描述、版本、发现、授权范围和速率限制。
- MCP Gateway：统一 MCP Server 认证、代理调用、参数校验、响应清洗、超时和审计。
- Connectors：GitHub、文件系统、浏览器自动化、项目管理系统、数据库和企业 API。
- Sandboxed Execution：隔离代码执行环境、文件系统范围、网络策略、CPU/内存/时限限制。

安全边界：模型生成的内容默认是不可信数据；不得因为模型提出工具调用就直接执行。所有副作用操作必须经过策略检查。代码执行与生产凭证隔离。MCP Server 和外部工具均视为独立信任边界。

当前状态：具备文本模型 API 适配与人工交接；应用程序不执行模型生成代码、不自动发送客户消息、不自动合并或部署。真正的工具执行代理、MCP Gateway 和安全沙箱属于后续能力。

### 2.4 治理与质量平面（Governance & Quality Plane）

- Tracing & Observability：任务级 Trace、Agent/模型/工具 Span、耗时、Token、错误和重放所需事件。
- Evals & Guardrails：任务验收、结构化输出校验、事实与来源核验、安全检查、Prompt Injection 防护和回归评估。
- Audit Log Store：身份、策略判定、审批、工具动作、目标资源、结果摘要和时间戳的审计记录。
- Human Review：独立审查者对关键交付物进行验收；执行 Agent 不得自我批准高风险结果。

Trace 与 Audit 分离：Trace 用于调试和性能分析；Audit 用于责任追踪和合规证明。不得将模型内部隐式推理链作为审计前提，应记录可审计的决策摘要、调用参数、结果和状态变更。

### 2.5 持久化与基础设施层（Data & Infrastructure）

- Task Queue / Workflow Engine：长任务、异步执行、重试、超时、断点恢复和调度。
- State Store：任务状态、版本、审批和工作流快照。
- Memory Store：短期会话缓存与长期检索索引。
- Artifact Store：输入、输出、测试证据和交付物的版本化存储。
- Audit Store：追加式审计记录与保留策略。

技术选型按需求触发：Redis、向量数据库、Kafka、Temporal、OpenTelemetry、Langfuse 等均为候选技术，不构成预先指定的强制依赖。先验证数据模型、可靠性和运维成本，再决定引入。

## 3. 核心运行闭环

`用户请求 → 身份认证 → 任务契约 → 编排与计划 → 策略检查 → 模型/工具执行 → 观察与验证 → 必要时人工审批 → 结果验收 → 审计归档`

每次执行必须具备：
- 唯一任务 ID 与关联 Trace ID；
- 明确的目标、范围、输入和输出契约；
- Agent、模型、工具及配置版本；
- 执行状态、重试次数和错误分类；
- 权限决策与审批记录；
- 可复现的测试/验收证据；
- 结果摘要、成本用量和最终状态。

任务状态建议统一为：queued、planned、running、waiting_approval、verifying、succeeded、failed、cancelled、stale。状态迁移必须由工作流规则驱动，不能由模型自由声明完成。

## 4. 参考架构模块映射

| 参考图模块 | SI 目标模块 | 演进要求 |
|---|---|---|
| Agent Gateway | Access Gateway | 统一入口、身份和请求治理 |
| Identity & Auth | Identity / RBAC | 用户、团队、服务身份与范围授权 |
| Agent Registry | Agent Registry | 角色、能力、版本、权限声明 |
| Agent Orchestrator | Workflow / Agent Orchestrator | 计划、委派、状态机、恢复 |
| LLM Router | Model Gateway | 模型路由、降级、用量与成本策略 |
| Memory Service | Context & Memory | 会话、项目、长期记忆及来源治理 |
| Permission Engine | Policy Engine | 每次动作前授权与最小权限 |
| Approval Queue | Human Approval | 高风险动作暂停与审批绑定 |
| Tool Registry | Tool Registry | 工具发现、Schema、版本和权限 |
| MCP Gateway | MCP Gateway | MCP 认证、代理、校验和审计 |
| MCP Servers | Connectors | 外部系统连接器 |
| Code Sandbox | Execution Sandbox | 隔离执行与资源限制 |
| Task Queue | Durable Workflow | 异步任务、持久化与恢复 |
| Tracing & Observability | Observability | Trace、指标、日志和运行回放 |
| Evals & Guardrails | Evaluation & Safety | 验收、红队、安全与回归评估 |
| Audit Log Store | Audit Ledger | 可追责、可检索的操作记录 |

## 5. 分阶段实施路线

### V1：可控的多 Agent 协作工作台（当前基线）

目标：跑通任务契约、人工协作、阶段审批和独立验收。

- 保留本地优先、Python 标准库运行基线。
- Agent 角色配置、任务输入/输出契约和版本绑定。
- 模型适配与按角色路由；模型调用必须显式授权数据发送。
- Git Worktree、GitHub Issue/PR、CI 与人工审查。
- 任务日志、质量门禁、失败阻断和审计摘要。
- 禁止自动合并、自动部署和无审批的副作用工具调用。

V1 完成标准：至少一条真实授权工程任务端到端通过，证据可复核，失败可阻断，审批可追溯。

### V1.x：治理与可观测性加固

- 统一任务/执行事件 Schema 和 Trace ID。
- 工具注册表静态化，工具白名单与 read/write 权限分级。
- 审批记录绑定任务版本、动作和资源。
- 结构化验收报告、独立审计 Agent 和回归评测集。
- 对密钥、敏感数据、Prompt Injection 和工具参数进行安全测试。

### V2：事件驱动与持久化工作流

- 事件驱动编排、异步任务和断点恢复。
- 多 Agent 委派、并发执行和依赖管理。
- 按实际规模引入持久化任务队列/工作流引擎。
- 项目记忆与知识检索，具备来源、权限和过期策略。
- MCP Gateway 与首批只读连接器；写操作逐步纳入审批。

### V3：企业级智能体操作系统

- 多用户、团队、租户隔离与 SSO。
- 动态策略引擎、在线审批队列和审计存储。
- 隔离执行沙箱与受控网络出口。
- 多模型路由优化、预算策略、供应商降级。
- 评测平台、持续回归、安全红队和运营看板。
- 可扩展的 Agent/Tool 市场与企业系统连接器。

阶段升级必须通过 ADR 记录架构决策；不得仅因参考图出现某项技术就提前引入。

## 6. 当前实现与目标能力的边界

当前仓库已有本地阶段工作流、人工审批、版本失效、文本模型 Provider、只读看板、测试和 GitHub PR 契约。它不是多租户服务，也不是通用自主执行 Agent Runtime。

当前明确禁止或尚未承诺：
- 不自动合并 PR、不自动部署生产；
- 不执行模型生成代码；
- 不自动发送客户消息或执行不可逆操作；
- 不将本地文件哈希等同于身份认证或防篡改审计；
- 不声称已有云端身份、在线审批、长期记忆、MCP 代理或生产级沙箱；
- 不将 Token/调用次数限制描述为费用金额硬上限。

任何改变上述信任边界的需求，必须先新增 ADR、威胁模型、测试和人工批准。

## 7. 架构验收指标

后续各版本至少跟踪：
- 任务完成率、一次验收通过率、返工率；
- 工具调用成功率、超时率、重试率；
- 高风险动作审批覆盖率（目标 100%）；
- 无授权动作拦截率（目标 100%）；
- Trace/审计事件完整率（关键动作目标 100%）；
- 单任务 Token、模型费用、运行时长；
- 回归评测通过率与安全测试拦截率；
- 任务失败恢复成功率。

所有指标应注明统计口径、样本量和时间范围，不能只报告单次演示结果。

## 8. 相关文档

- `README.md`：仓库使用与当前能力边界
- `docs/ARCHITECTURE.md`：当前已实现架构与信任边界
- `docs/PRD.md`：产品需求
- `docs/ACCEPTANCE.md`：验收要求
- `docs/VALIDATION.md`：验证证据
- `docs/adr/`：具体技术选型与架构决策记录

本文件定义目标架构，不替代当前实现文档；实现状态以代码、测试和验证记录为准。

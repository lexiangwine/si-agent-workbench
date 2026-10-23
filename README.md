# SI Agent Workbench

面向 VS Code 多 Agent 协作的本地工作台：用任务契约管理输入、角色、交付物和人工验收。版本 **0.1.0**，Python **3.11+**，运行时无第三方依赖。

## 已实现
- 两条流程：工程协作；需求 → 技术 → 商务 → 实施 → 风险 → 交付草稿。
- 手工协作：导出完整任务 Prompt，交给已有 VS Code Agent，再导入结果。
- API接入：OpenAI Responses、Claude Messages、Grok/DeepSeek Chat Completions，按角色路由。
- 人工阶段门禁：审批绑定输入、输出、角色规则和上游审批版本；变化后下游失效。
- 本地只读看板：项目、阶段、成果预览，支持桌面与窄屏。
- 工程质量：测试、有限密钥扫描、PR契约、工作树与任务模板。

工作台编排文档和审查交付；已有编程 Agent 在独立工作树修改代码并提供测试证据。本程序不执行模型输出的代码、不发客户消息、不自动合并或部署。

## 3分钟离线启动

```bash
git clone https://github.com/lexiangwine/si-agent-workbench.git
cd si-agent-workbench
# PR合并前切换到实现分支
git switch feat/workbench-foundation
python3 -m workbench doctor
python3 -m workbench demo
python3 -m workbench serve
```

打开 **http://127.0.0.1:8765**。demo仅生成虚构占位成果和模拟审批，无联网、无模型费用，不能作为客户交付。重复演示用新编号：`python3 -m workbench demo --name demo-002`。

Windows可用`py -3`替代`python3`；Bash脚本用于macOS/Linux或Git Bash。

## 在 VS Code 使用

打开`si-agent-workbench.code-workspace`，通过“终端 → 运行任务”检查、演示、启动看板、导出Prompt、查看状态和测试。设置`si.python`为本机Python可执行文件；默认python3。

不自动安装或登录Agent扩展。将导出的完整任务交给现有Codex、Claude或其他Agent；所有会话遵循同一输入版本和完成定义。

## 第一条正式流程

客户授权资料只放本地workspace，下面用虚构示例练习：

```bash
python3 -m workbench new p001 --workflow delivery --brief examples/brief.md
python3 -m workbench prompt p001 requirements
```

把输出的`workspace/projects/p001/prompts/requirements.md`交给Agent。结果需包含契约要求的二级标题，保存至`workspace/requirements-result.md`后：

```bash
python3 -m workbench import p001 requirements --file workspace/requirements-result.md
python3 -m workbench approve p001 requirements --by "业务负责人" --note "已核对范围、来源和未决事项"
python3 -m workbench prompt p001 technical
python3 -m workbench status p001
python3 -m workbench report p001
```

后续阶段：technical、commercial、implementation、risk、delivery。工程流程用`--workflow engineering`，阶段为plan、design、review、handoff。

需求变更后重新导出Prompt、复核成果再导入；受影响的后续成果和审批必须重做。导入旧Prompt产生的结果会被拒绝。

## 真实模型接入

```bash
cp config/providers.example.json config/providers.local.json
```

在本机设置需要的`*_API_KEY`和`*_MODEL`变量，按账户选择可用模型；配置roles只是路由示例，可以先将所有角色指向一个供应商。变量和官方协议来源见[模型接入](docs/PROVIDERS.md)。

```bash
python3 -m workbench run p001 requirements --execute --data-approved
```

只执行当前阶段一次真实请求，结果仍需人工审批。`--data-approved`表示操作者已确认上下文可以发送给所选供应商。无两个显式参数、有效配置、模型名或密钥时不发请求。不自动加载.env、不借用网页登录态、不自动重试。

**目前完成离线协议测试，尚未使用你的真实密钥做线上联调。** 真实模型访问和计费由供应商账户决定。

## 目录和数据

|目录|作用|
|---|---|
|agents/ workflows/|角色规则与两条阶段流程|
|workbench/|CLI、状态机、接口与本地看板|
|config/|无密钥的配置示例|
|templates/delivery/|原声画科技通用交付模板|
|docs/tasks/ scripts/ tests/|任务契约、工程工具与测试|
|workspace/|本地资料、成果、审批和运行记录，不进入Git|

项目位于`workspace/projects/<编号>/`：brief.md保存需求，workflow.json固定创建时流程，state.json记录结果和审批。该文件模式不提供远程协作、身份认证或防篡改签名。

## 验证

```bash
bash scripts/check.sh
python3 tools/quality_gate.py --scan
```

扫描面向跟踪文件，新代码先git add再扫描。跨平台测试：`python3 -m unittest discover -s tests -v`。

遵循[AGENTS.md](AGENTS.md)：任务契约 → 独立分支/工作树 → 实现与证据 → 关联Issue的PR → 人工审核 → 授权合并。不把客户数据、密钥、本地配置和workspace强制加入Git。

## 文档与边界

[产品范围](docs/PRD.md) · [架构](docs/ARCHITECTURE.md) · [运维](docs/DEPLOY.md) · [模型接入](docs/PROVIDERS.md) · [协作方式](docs/AGENT_PROMPTS.md) · [验收](docs/ACCEPTANCE.md) · [验证记录](docs/VALIDATION.md)

未实现云端账号、租户隔离、在线协同审批、自动编码执行沙箱、金额费用硬上限、PDF/Word自动排版和生产监控。先验证一条真实授权流程，再按任务扩展。

# 模型接入与费用边界

## 两种入口
已有VS Code Agent读取导出Prompt、生成Markdown后import，不需本程序配置API。API模式则复制providers.example.json至providers.local.json，按角色选供应商，在本机设置变量。

|供应商|密钥变量|模型变量|协议|
|---|---|---|---|
|OpenAI|OPENAI_API_KEY|OPENAI_MODEL|Responses|
|Claude|ANTHROPIC_API_KEY|ANTHROPIC_MODEL|Messages|
|Grok|XAI_API_KEY|XAI_MODEL|Chat Completions|
|DeepSeek|DEEPSEEK_API_KEY|DEEPSEEK_MODEL|Chat Completions|

Claude可选ANTHROPIC_WORKSPACE_ID，是否必须取决于账户授权。模型名不预设，按账户可用模型和接口填写。roles是路由示例，不是能力排名，可先统一一个供应商。

不自动加载.env，不借用网页登录态，不自动安装或执行Codex/Claude CLI。现有工具通过手工任务契约交接；API使用独立凭证和供应商计费，不承诺订阅抵扣。

## 调用
先检查导出Prompt、客户许可、明确端点和主机、模型与账户预算，再run并传--execute和--data-approved。程序不执行工具，不抓取链接，不验证模型引用真实性。输出先pending_review，须人审。

每项目远程尝试最多20次，失败也计数；累计输入≤120KB，成果≤150KB，响应≤2MB，输出Token上限64—16384，网络超时可配1—120秒。模型上下文可能更小。次数/Token不是金额上限，应配置供应商账户限额并核对账单。超时可能已计费，不自动重试；截断、空结果和工具请求拒绝成为完整成果。

## 官方协议来源
设计核对日期2026-10-23；完成离线协议模拟，尚未用用户密钥验证线上账户。

- OpenAI文本与Responses：https://developers.openai.com/api/docs/guides/text
- Claude Messages：https://platform.claude.com/docs/en/api/messages/create
- Claude认证：https://platform.claude.com/docs/en/manage-claude/authentication
- Grok兼容端点：https://docs.x.ai/developers/model-capabilities/legacy/chat-completions
- DeepSeek：https://api-docs.deepseek.com/

Grok文档将Chat Completions列为legacy兼容接口；本适配器仅实现其文本路径，迁移Responses需新增适配与测试。Claude示例固定2023-06-01协议，可按官方支持范围调整版本并联调。

"""Minimal text-only provider adapters. Never execute returned code or tools."""
from dataclasses import dataclass
import json
import os
import re
import socket
from urllib import error, parse, request

from .storage import WorkbenchError, read_json

MAX_RESPONSE = 2_000_000


@dataclass
class Result:
    text: str
    usage: dict


class NoRedirect(request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise WorkbenchError("拒绝模型接口重定向，请核对明确配置的 HTTPS 地址。")


def resolve_env(value):
    if isinstance(value, str) and value.startswith("env:"):
        name = value[4:]
        if not re.fullmatch(r"[A-Z][A-Z0-9_]*", name):
            raise WorkbenchError("环境变量名称无效。")
        return os.environ.get(name, "")
    return value


def profile_for(path, role):
    conf = read_json(path)
    if not isinstance(conf, dict) or not isinstance(conf.get("roles", {}), dict) or not isinstance(conf.get("providers"), dict):
        raise WorkbenchError("供应商配置必须包含对象类型的 providers 和 roles。")
    selected = conf.get("roles", {}).get(role, conf.get("default_provider"))
    if not isinstance(selected, str):
        raise WorkbenchError("供应商路由必须是名称字符串。")
    source = conf.get("providers", {}).get(selected)
    if not isinstance(source, dict):
        raise WorkbenchError("角色未配置可用供应商：" + role)
    profile = {k: resolve_env(v) for k, v in source.items()}
    if "api_key" in profile:
        raise WorkbenchError("配置只允许 api_key_env，禁止明文 API 密钥。")
    if not re.fullmatch(r"[A-Z][A-Z0-9_]*", str(profile.get("api_key_env", ""))):
        raise WorkbenchError("api_key_env 需要合法的环境变量名称。")
    if not profile.get("model"):
        raise WorkbenchError("模型未配置，请设置供应商对应的 MODEL 环境变量。")
    try:
        cap = int(profile.get("max_output_tokens", 2000))
        timeout = int(profile.get("timeout_seconds", 90))
    except (ValueError, TypeError) as exc:
        raise WorkbenchError("Token 或超时配置无效。") from exc
    if not 64 <= cap <= 16384 or not 1 <= timeout <= 120:
        raise WorkbenchError("输出 Token 范围64—16384，超时范围1—120秒。")
    profile["max_output_tokens"] = cap
    profile["timeout_seconds"] = timeout
    validate_endpoint(profile)
    return selected, profile


def validate_endpoint(profile):
    endpoint = profile.get("endpoint", "")
    if not isinstance(endpoint, str):
        raise WorkbenchError("模型接口地址无效。")
    parts = parse.urlsplit(endpoint)
    if (parts.scheme != "https" or not parts.hostname or parts.username or parts.password
            or parts.query or parts.fragment):
        raise WorkbenchError("模型接口必须是无账号、查询参数或片段的 HTTPS 地址。")
    hosts = profile.get("allowed_hosts", [])
    if not isinstance(hosts, list) or parts.hostname not in hosts:
        raise WorkbenchError("模型接口主机未在该配置的 allowed_hosts 中明确允许。")


def build_request(profile, prompt):
    validate_endpoint(profile)
    key = os.environ.get(profile["api_key_env"], "")
    if not key:
        raise WorkbenchError("缺少环境变量：" + profile["api_key_env"])
    api = profile.get("api")
    headers = {"Content-Type": "application/json", "Authorization": "Bearer " + key}
    body = {"model": profile["model"]}
    cap = profile["max_output_tokens"]
    if api == "responses":
        body.update(input=prompt, max_output_tokens=cap, store=False)
    elif api == "chat_completions":
        field = profile.get("token_field", "max_tokens")
        if field not in ("max_tokens", "max_completion_tokens"):
            raise WorkbenchError("Token 参数只能是 max_tokens 或 max_completion_tokens。")
        body.update(messages=[{"role": "user", "content": prompt}], stream=False)
        body[field] = cap
    elif api == "anthropic_messages":
        body.update(messages=[{"role": "user", "content": prompt}], max_tokens=cap)
        headers["anthropic-version"] = profile.get("api_version", "2023-06-01")
        workspace = profile.get("workspace_id")
        if workspace:
            headers["anthropic-workspace-id"] = workspace
    else:
        raise WorkbenchError("不支持的 API 协议。")
    return request.Request(profile["endpoint"], json.dumps(body).encode(), headers, method="POST")


def parse_result(api, data):
    try:
        if not isinstance(data, dict) or data.get("error"):
            raise ValueError("provider error")
        if api == "responses":
            if data.get("status") != "completed":
                raise WorkbenchError("模型响应未完成，不能作为完整交付导入。")
            text = "\n".join(c["text"] for x in data.get("output", [])
                             if x.get("type") == "message" for c in x.get("content", [])
                             if c.get("type") == "output_text")
        elif api == "anthropic_messages":
            if data.get("stop_reason") != "end_turn":
                raise WorkbenchError("Claude 响应被截断或要求工具操作，请调整后重新运行。")
            text = "\n".join(x["text"] for x in data["content"] if x.get("type") == "text")
        elif api == "chat_completions":
            choice = data["choices"][0]
            if choice.get("finish_reason") != "stop":
                raise WorkbenchError("模型响应未正常结束，不能作为完整交付导入。")
            text = choice["message"]["content"]
        else:
            raise ValueError("unknown api")
        if not isinstance(text, str) or not text.strip():
            raise ValueError("empty output")
        usage = data.get("usage") or {}
        # Persist counts only. Do not retain raw response metadata or credentials.
        safe_usage = {k: v for k, v in usage.items() if isinstance(v, int) and not isinstance(v, bool)}
        return Result(text.strip() + "\n", safe_usage)
    except (KeyError, IndexError, TypeError, ValueError, AttributeError) as exc:
        raise WorkbenchError("模型返回的数据结构或文本无效。") from exc


def complete(profile, prompt):
    req = build_request(profile, prompt)
    opener = request.build_opener(NoRedirect())
    try:
        with opener.open(req, timeout=profile["timeout_seconds"]) as response:
            raw = response.read(MAX_RESPONSE + 1)
            if len(raw) > MAX_RESPONSE:
                raise WorkbenchError("模型响应过大。")
        data = json.loads(raw)
    except error.HTTPError as exc:
        # Do not display raw provider bodies; they may reflect sensitive input.
        raise WorkbenchError(f"模型接口 HTTP {exc.code}；本次未自动重试，请检查账户与服务。") from None
    except (error.URLError, TimeoutError, socket.timeout, OSError):
        raise WorkbenchError("模型请求失败或超时；可能已经计费，不自动重试。") from None
    except (json.JSONDecodeError, UnicodeDecodeError):
        raise WorkbenchError("模型响应不是有效 JSON。") from None
    return parse_result(profile["api"], data)

"""Unified task contract, schema v2.

Hand-written validator using only the standard library (no jsonschema).
The format itself is specified in workflows/schema-v2.json; this module
enforces the same rules in code. v1 contracts (no contract_version field,
or contract_version 1) keep the old validation rules and keep working;
only v2 files gain inputs / acceptance validation.
"""
import json
import re

from .storage import WorkbenchError, identifier, managed, read_json

CONTRACT_VERSION = 2
GATE_PATTERN = re.compile(r"^[A-Z]{1,2}[0-9]+$")

INPUT_KINDS = ("brief", "artifact", "approval", "file")

# check name -> (verifier id, allowed params with expected types)
CHECKS = {
    "required_sections": ("V1", {}),
    "section_min_chars": ("V1", {"min_chars": int}),
    "no_placeholder": ("V6", {}),
    "input_version_match": ("V2", {}),
    "upstream_approvals_match": ("V3", {}),
    "approval_chain": ("V3", {}),
    "max_bytes": ("V5", {"max_bytes": int}),
}

DEFAULT_ACCEPTANCE = [
    {"check": "required_sections"},
    {"check": "section_min_chars", "min_chars": 20},
    {"check": "no_placeholder"},
    {"check": "input_version_match"},
    {"check": "upstream_approvals_match"},
]

FINAL_STAGE_ACCEPTANCE = [{"check": "approval_chain"}]


def default_acceptance(is_final=False):
    """The acceptance list a stage gets when it declares none."""
    items = [dict(x) for x in DEFAULT_ACCEPTANCE]
    if is_final:
        items.extend(dict(x) for x in FINAL_STAGE_ACCEPTANCE)
    return items


def acceptance_for(stage, is_final=False):
    """Acceptance list for a stage: declared one, or the default."""
    acceptance = stage.get("acceptance")
    if acceptance is None:
        return default_acceptance(is_final)
    return acceptance


def _fail(where, message):
    raise WorkbenchError("契约校验失败：" + where + " " + message)


def _non_empty_string(value):
    return isinstance(value, str) and value.strip()


def _check_positive_int(where, item, key):
    if key in item:
        value = item[key]
        if not isinstance(value, int) or isinstance(value, bool) or value <= 0:
            _fail(where, key + " 必须是正整数。")


def _validate_stage_common(index, stage, seen):
    where = "阶段[%d]" % index
    if not isinstance(stage, dict):
        _fail(where, "必须是 JSON 对象。")
    if not all(_non_empty_string(stage.get(k)) for k in ("title", "gate")):
        _fail(where, "必须包含有效标题与门禁编号。")
    try:
        sid = identifier(stage.get("id"))
    except WorkbenchError:
        _fail(where, "编号无效（小写字母、数字、连字符和下划线，长度 1—64）。")
    try:
        identifier(stage.get("role"))
    except WorkbenchError:
        _fail(where, "角色编号无效。")
    if sid in seen:
        _fail(where, "阶段编号重复：" + sid)
    seen.add(sid)
    sections = stage.get("sections")
    if not isinstance(sections, list) or not sections:
        _fail(where, "未定义交付章节。")
    if not all(_non_empty_string(x) for x in sections):
        _fail(where, "交付章节名称无效。")
    if len(set(sections)) != len(sections):
        _fail(where, "交付章节名称重复。")
    return sid


def _validate_stage_v2(root, index, stage, sid, stage_ids):
    where = "阶段 " + sid
    if not GATE_PATTERN.match(stage["gate"]):
        _fail(where, "门禁编号格式无效，应为字母加数字，如 G1、R1、E3。")
    role_path = managed(root, "agents", stage["role"] + ".md")
    if not role_path.is_file():
        _fail(where, "角色文件不存在：agents/" + stage["role"] + ".md。")
    inputs = stage.get("inputs")
    if inputs is not None:
        if not isinstance(inputs, list):
            _fail(where, "inputs 必须是列表。")
        for pos, item in enumerate(inputs):
            at = "%s inputs[%d]" % (where, pos)
            if not isinstance(item, dict) or not _non_empty_string(item.get("name")):
                _fail(at, "必须包含非空输入名。")
            kind = item.get("kind")
            if kind not in INPUT_KINDS:
                _fail(at, "kind 必须是 brief、artifact、approval、file 之一。")
            if "required" in item and not isinstance(item["required"], bool):
                _fail(at, "required 必须是布尔值。")
            if kind == "artifact":
                target = item.get("from_stage")
                if not isinstance(target, str) or target not in stage_ids:
                    _fail(at, "artifact 输入的 from_stage 必须指向本流程内已定义的阶段。")
            if kind == "file":
                path = item.get("path")
                if not isinstance(path, str) or not path.strip():
                    _fail(at, "file 输入必须声明 path。")
                try:
                    managed(root, path)
                except WorkbenchError:
                    _fail(at, "file 输入的 path 不在工作区内或使用了符号链接：" + path)
    acceptance = stage.get("acceptance")
    if acceptance is not None:
        if not isinstance(acceptance, list):
            _fail(where, "acceptance 必须是列表。")
        for pos, item in enumerate(acceptance):
            at = "%s acceptance[%d]" % (where, pos)
            if not isinstance(item, dict):
                _fail(at, "必须是 JSON 对象。")
            check = item.get("check")
            if check not in CHECKS:
                _fail(at, "未知的确定性检查名：" + str(check) + "。")
            for key in CHECKS[check][1]:
                _check_positive_int(at, item, key)


def validate_contract(root, data):
    """Validate a contract dict; return a normalized copy.

    v1 (no contract_version, or 1): old rules only.
    v2 (contract_version 2): full rules, including inputs/acceptance.
    Any other version raises WorkbenchError.
    """
    if not isinstance(data, dict):
        raise WorkbenchError("流程必须是 JSON 对象。")
    version = data.get("contract_version")
    if version is None:
        version = 1
    if not isinstance(version, int) or isinstance(version, bool) or version not in (1, 2):
        raise WorkbenchError("契约版本不受支持：" + str(version) + "。")
    stages = data.get("stages", [])
    if not isinstance(stages, list) or not stages or len(stages) > 20:
        raise WorkbenchError("流程需要 1—20 个阶段。")
    if version == 2:
        if not _non_empty_string(data.get("name")) or not _non_empty_string(data.get("version")):
            raise WorkbenchError("契约校验失败：v2 契约必须包含非空 name 与 version。")
    seen = set()
    stage_ids = set()
    for stage in stages:
        if isinstance(stage, dict) and isinstance(stage.get("id"), str):
            stage_ids.add(stage["id"])
    normalized = json.loads(json.dumps(data, ensure_ascii=False))
    normalized["contract_version"] = version
    for index, stage in enumerate(normalized["stages"]):
        sid = _validate_stage_common(index, stage, seen)
        if version == 2:
            _validate_stage_v2(root, index, stage, sid, stage_ids)
    return normalized


def load_contract(root, name):
    """Load and validate workflows/<name>.json; return the normalized contract."""
    data = read_json(managed(root, "workflows", identifier(name) + ".json"))
    return validate_contract(root, data)

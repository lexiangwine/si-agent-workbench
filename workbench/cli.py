"""Command-line entry point; runs from a clone without pip install."""
import argparse
import json
from pathlib import Path
import sys

from .engine import Engine
from .storage import WorkbenchError, read_text

ROOT = Path(__file__).resolve().parents[1]


def parser():
    p = argparse.ArgumentParser(prog="python3 -m workbench", description="SI Agent 工作台")
    sub = p.add_subparsers(dest="command", required=True)
    sub.add_parser("doctor", help="检查 Python、目录、Git 和流程配置（不联网）")
    sub.add_parser("list", help="列出本地项目")
    a = sub.add_parser("new", help="新建正式项目")
    a.add_argument("name")
    a.add_argument("--workflow", choices=("delivery", "engineering"), default="delivery")
    a.add_argument("--brief", required=True, type=Path)
    a = sub.add_parser("demo", help="运行虚构的离线演示，不调用模型")
    a.add_argument("--name", default="demo-delivery")
    a.add_argument("--workflow", choices=("delivery", "engineering"), default="delivery")
    a = sub.add_parser("status")
    a.add_argument("name")
    a.add_argument("--json", action="store_true")
    a = sub.add_parser("prompt", help="导出任务契约，交给现有 VS Code Agent")
    a.add_argument("name")
    a.add_argument("stage")
    a = sub.add_parser("import", help="导入人工或现有 Agent 完成的 Markdown")
    a.add_argument("name")
    a.add_argument("stage")
    a.add_argument("--file", type=Path, required=True)
    a = sub.add_parser("run", help="执行一次真实 API 请求，输出仍需人工审批")
    a.add_argument("name")
    a.add_argument("stage")
    a.add_argument("--config", type=Path, default=ROOT / "config/providers.local.json")
    a.add_argument("--execute", action="store_true")
    a.add_argument("--data-approved", action="store_true")
    a = sub.add_parser("approve", help="由负责人审核交付后记录阶段审批")
    a.add_argument("name")
    a.add_argument("stage")
    a.add_argument("--by", required=True)
    a.add_argument("--note", required=True)
    a = sub.add_parser("report", help="生成本地项目状态报告")
    a.add_argument("name")
    a = sub.add_parser("serve", help="启动仅本机可访问的只读看板")
    a.add_argument("--port", type=int, default=8765)
    return p


def display(value, as_json=False):
    if as_json:
        print(json.dumps(value, ensure_ascii=False, indent=2))
        return
    print(f"项目 {value['name']} | {value['workflow']} | {value['mode']} | {value['status']}")
    for stage in value["stages"]:
        print(f"  {stage['gate']:3} {stage['id']:16} {stage['status']:16} {stage['title']}")


def main(argv=None):
    a = parser().parse_args(argv)
    engine = Engine(ROOT)
    try:
        if a.command == "doctor":
            import subprocess
            from .engine import workflow
            if sys.version_info < (3, 11):
                raise WorkbenchError("需要 Python 3.11 或更新版本。")
            for name in ("delivery", "engineering"):
                for stage in workflow(ROOT, name)["stages"]:
                    read_text(ROOT / "agents" / (stage["role"] + ".md"))
            proc = subprocess.run(["git", "--version"], capture_output=True, text=True, check=True)
            print("PASS: Python", sys.version.split()[0], "|", proc.stdout.strip())
            print("PASS: 两条流程与角色文件齐全；未联网、未读取或打印 API 密钥。")
        elif a.command == "list":
            names = engine.store.names()
            for name in names:
                value = engine.status(name)
                print(name, value["workflow"], value["mode"], value["status"])
            if not names:
                print("尚无项目。先运行 python3 -m workbench demo")
        elif a.command == "new":
            display(engine.create(a.name, a.workflow, read_text(a.brief)))
        elif a.command == "demo":
            display(engine.demo(a.name, a.workflow))
            print("这是模拟审批和占位内容；没有真实模型调用。")
        elif a.command == "status":
            display(engine.status(a.name), a.json)
        elif a.command == "prompt":
            print(engine.prompt(a.name, a.stage))
        elif a.command == "import":
            display(engine.ingest(a.name, a.stage, read_text(a.file, 150_000)))
        elif a.command == "run":
            display(engine.run(a.name, a.stage, a.config, a.execute, a.data_approved))
        elif a.command == "approve":
            display(engine.approve(a.name, a.stage, a.by, a.note))
        elif a.command == "report":
            print(engine.report(a.name))
        elif a.command == "serve":
            from .dashboard import serve
            serve(engine, a.port)
        return 0
    except (WorkbenchError, OSError, ValueError) as exc:
        print("BLOCKED:", exc, file=sys.stderr)
        return 2
    except KeyboardInterrupt:
        print("\n已停止。", file=sys.stderr)
        return 130


if __name__ == "__main__":
    raise SystemExit(main())

"""Atomic local records and a per-project writer lock (no external packages)."""
from contextlib import contextmanager
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import tempfile


class WorkbenchError(Exception):
    """An actionable, safe-to-display user error."""


def now():
    return datetime.now(timezone.utc).isoformat()


def digest(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def identifier(value):
    if not isinstance(value, str) or not re.fullmatch(r"[a-z0-9][a-z0-9_-]{0,63}", value):
        raise WorkbenchError("编号只能包含小写字母、数字、连字符和下划线，长度1—64。")
    return value


def managed(root, *parts):
    """Reject traversals and symlinks in managed paths, including parent folders."""
    root = Path(root).absolute()
    path = root.joinpath(*parts)
    try:
        path.absolute().relative_to(root)
    except ValueError as exc:
        raise WorkbenchError("路径超出工作区。") from exc
    if ".." in path.parts:
        raise WorkbenchError("不允许父目录路径。")
    for current in (path, *path.parents):
        if current.is_symlink():
            raise WorkbenchError("受管理路径不能使用符号链接。")
    return path


def read_text(path, limit=200_000):
    path = Path(path)
    if path.is_symlink() or not path.is_file():
        raise WorkbenchError("文件不存在或是符号链接：" + path.name)
    if path.stat().st_size > limit:
        raise WorkbenchError("文本过大，请缩小资料范围：" + path.name)
    try:
        return path.read_text(encoding="utf-8")
    except UnicodeDecodeError as exc:
        raise WorkbenchError("仅支持 UTF-8 文本：" + path.name) from exc


def atomic_text(path, text):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=".writing-")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            stream.write(text)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)


def read_json(path):
    try:
        return json.loads(read_text(path, 2_000_000))
    except json.JSONDecodeError as exc:
        raise WorkbenchError("JSON 格式错误：" + Path(path).name) from exc


def write_json(path, value):
    atomic_text(path, json.dumps(value, ensure_ascii=False, indent=2) + "\n")


class Store:
    def __init__(self, root):
        self.root = Path(root).absolute()

    def project(self, name):
        return managed(self.root, "workspace", "projects", identifier(name))

    def exists(self, name):
        return self.project(name).is_dir()

    def load(self, name):
        return read_json(managed(self.project(name), "state.json"))

    def save(self, name, state):
        write_json(managed(self.project(name), "state.json"), state)

    def names(self):
        folder = managed(self.root, "workspace", "projects")
        if not folder.exists():
            return []
        return sorted(p.name for p in folder.iterdir() if p.is_dir() and not p.is_symlink())

    @contextmanager
    def lock(self, name, create=False):
        folder = self.project(name)
        if create:
            folder.parent.mkdir(parents=True, exist_ok=True)
            try:
                folder.mkdir(mode=0o700)
            except FileExistsError as exc:
                raise WorkbenchError("项目已存在，请选择另一个编号。") from exc
        if not folder.is_dir():
            raise WorkbenchError("项目不存在，请先 new。")
        lock_path = managed(folder, ".lock")
        try:
            fd = os.open(lock_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        except FileExistsError as exc:
            raise WorkbenchError("项目正在被写入；如进程已异常退出，请按运维文档排查锁文件。") from exc
        try:
            with os.fdopen(fd, "w") as stream:
                stream.write(str(os.getpid()))
            yield folder
        finally:
            lock_path.unlink(missing_ok=True)

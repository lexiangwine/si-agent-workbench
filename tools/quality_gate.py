#!/usr/bin/env python3
"""Minimal dependency-free PR quality checks. Not a substitute for SAST."""
import argparse
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REQUIRED = ('AGENTS.md', 'docs/PRD.md', 'docs/ARCHITECTURE.md', '.github/PULL_REQUEST_TEMPLATE.md')
SECURITY_PATTERNS = {
    'private-key': re.compile(r'-----BEGIN (?:RSA |EC |OPENSSH |DSA )?PRIVATE KEY-----'),
    'github-token': re.compile(r'gh[pousr]_[A-Za-z0-9_]{25,}'),
    'aws-access-key': re.compile(r'\b(?:AKIA|ASIA)[A-Z0-9]{16}\b'),
}
EXCLUDED = {'.git', '.venv', 'node_modules', '__pycache__', '.pytest_cache'}

def forbidden_path(path):
    path = Path(path)
    return ('workspace' in path.parts or path.name.endswith('.local.json') or
            (path.name != '.env.example' and
             (path.name == '.env' or path.name.startswith('.env.'))))

def tracked_files():
    proc = subprocess.run(['git', 'ls-files', '-z'], cwd=ROOT, capture_output=True)
    if proc.returncode:
        raise RuntimeError('Git repository required for tracked-file security scan')
    return [ROOT / p.decode('utf-8', 'surrogateescape') for p in proc.stdout.split(b'\0') if p]

def scan_text(text):
    return [name for name, regex in SECURITY_PATTERNS.items() if regex.search(text)]

def run():
    problems = []
    for item in REQUIRED:
        if not (ROOT / item).is_file():
            problems.append('required file missing: ' + item)
    for file in tracked_files():
        if any(part in EXCLUDED for part in file.parts):
            continue
        if forbidden_path(file.relative_to(ROOT)):
            problems.append('tracked private/runtime file: ' + str(file.relative_to(ROOT)))
        if file.is_symlink() or not file.is_file() or file.stat().st_size > 1024 * 1024:
            continue
        try:
            value = file.read_text(encoding='utf-8')
        except (UnicodeDecodeError, OSError):
            continue
        for kind in scan_text(value):
            problems.append(f'{file.relative_to(ROOT)}: potential {kind}')
    return problems

def main():
    p=argparse.ArgumentParser()
    p.add_argument('--scan',action='store_true')
    a=p.parse_args()
    try: problems=run()
    except RuntimeError as exc:
        print('BLOCKER:',exc,file=sys.stderr);return 2
    if problems:
        for item in problems:print('FAIL:',item,file=sys.stderr)
        return 1
    print('PASS: required files and limited tracked-file secret patterns')
    return 0
if __name__=='__main__':sys.exit(main())

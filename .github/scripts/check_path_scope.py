#!/usr/bin/env python3
from __future__ import annotations

import fnmatch
import os
import re
import subprocess
import sys
from pathlib import Path

import yaml


def run(cmd: list[str]) -> str:
    result = subprocess.run(cmd, check=True, capture_output=True, text=True)
    return result.stdout.strip()


def load_config(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def changed_files(base_sha: str, head_sha: str) -> list[str]:
    out = run(["git", "diff", "--name-only", f"{base_sha}...{head_sha}"])
    if not out:
        return []
    return [line.strip() for line in out.splitlines() if line.strip()]


def parse_module(pr_title: str, pr_body: str) -> str | None:
    patterns = [
        re.compile(r"\[module:([a-z0-9_-]+)\]", re.IGNORECASE),
        re.compile(r"模块\s*[:：]\s*`?([a-z0-9_-]+)`?", re.IGNORECASE),
        re.compile(r"module\s*[:：]\s*`?([a-z0-9_-]+)`?", re.IGNORECASE),
    ]
    for text in (pr_title or "", pr_body or ""):
        for pat in patterns:
            match = pat.search(text)
            if match:
                return match.group(1).lower()
    return None


def parse_yes_no_answer(pr_body: str, question: str) -> str | None:
    escaped = re.escape(question)
    patterns = [
        re.compile(rf"{escaped}.*?\*\*(是|否)\s*/\s*(是|否)\*\*", re.IGNORECASE),
        re.compile(rf"{escaped}\s*[:：]\s*(是|否)", re.IGNORECASE),
        re.compile(rf"{escaped}.*?\*\*(是|否)\*\*", re.IGNORECASE),
    ]
    for pattern in patterns:
        match = pattern.search(pr_body)
        if match:
            for group in match.groups():
                if group in {"是", "否"}:
                    return group
    return None


def has_cross_package_approval(pr_body: str) -> bool:
    return bool(re.search(r"跨包越界批准\s*[:：]\s*APPROVED\s+by\s+@[-a-zA-Z0-9_/.]+", pr_body or ""))


def validate_compliance_answers(pr_body: str) -> tuple[list[str], dict[str, str]]:
    required_questions = [
        "本 PR 是否仅修改授权白名单路径？",
        "是否附带风险说明、回滚步骤、验证证据？",
        "是否有跨包越界改动？如有，是否获得额外批准？",
        "本次变更是否可被独立回滚（不影响其他包）？",
    ]
    errors: list[str] = []
    answers: dict[str, str] = {}
    for question in required_questions:
        answer = parse_yes_no_answer(pr_body, question)
        if answer is None:
            errors.append(f"缺少合规问答答案：{question}（请填写 是/否）")
        else:
            answers[question] = answer
    return errors, answers


def is_allowed(path: str, patterns: list[str]) -> bool:
    return any(fnmatch.fnmatch(path, pattern) for pattern in patterns)


def main() -> int:
    config = load_config(Path(".github/module-whitelist.yml"))

    base_sha = os.environ.get("BASE_SHA", "")
    head_sha = os.environ.get("HEAD_SHA", "")
    pr_title = os.environ.get("PR_TITLE", "")
    pr_body = os.environ.get("PR_BODY", "")

    if not base_sha or not head_sha:
        print("::error::BASE_SHA / HEAD_SHA 未提供")
        return 2

    module = parse_module(pr_title, pr_body)
    if not module:
        print("::error::未在 PR 标题或描述中找到模块声明。请使用 [module:<name>] 或填写 '模块: <name>'")
        return 1

    modules = config.get("modules", {})
    if module not in modules:
        print(f"::error::未知模块 '{module}'。可选模块: {', '.join(sorted(modules.keys()))}")
        return 1

    answer_errors, answers = validate_compliance_answers(pr_body)
    if answer_errors:
        for err in answer_errors:
            print(f"::error::{err}")
        return 1

    module_patterns = modules[module].get("paths", [])
    global_patterns = config.get("global_allowlist", [])
    allowed_patterns = [*module_patterns, *global_patterns]

    files = changed_files(base_sha, head_sha)
    violations = [p for p in files if not is_allowed(p, allowed_patterns)]

    print(f"模块: {module}")
    print("允许路径模式:")
    for p in allowed_patterns:
        print(f"  - {p}")

    if not files:
        print("无变更文件，检查通过。")
        return 0

    print("变更文件:")
    for f in files:
        print(f"  - {f}")

    answer_scope = answers["本 PR 是否仅修改授权白名单路径？"]
    answer_evidence = answers["是否附带风险说明、回滚步骤、验证证据？"]
    answer_cross = answers["是否有跨包越界改动？如有，是否获得额外批准？"]
    answer_rollback = answers["本次变更是否可被独立回滚（不影响其他包）？"]

    if answer_evidence != "是":
        print("::error::合规问答要求：必须附带风险说明、回滚步骤、验证证据。")
        return 1

    if answer_rollback != "是":
        print("::error::合规问答要求：变更必须可独立回滚，当前答案为“否”。")
        return 1

    if violations and answer_scope == "是":
        print("::error::合规问答与代码变更不一致：填写了“仅修改白名单路径=是”，但检测到越界改动。")
        for v in violations:
            print(f"  - {v}")
        return 1

    if not violations and answer_scope == "否":
        print("::error::合规问答与代码变更不一致：填写了“仅修改白名单路径=否”，但未检测到越界改动。")
        return 1

    if violations:
        if answer_cross != "是":
            print("::error::检测到跨包越界改动，但合规问答未标记为“是”。")
            return 1
        if not has_cross_package_approval(pr_body):
            print("::error::检测到跨包越界改动，请补充“跨包越界批准: APPROVED by @owner_or_maintainer（原因）”。")
            return 1
        print("::warning::检测到越界改动，但已提供跨包越界批准记录。")
    else:
        if answer_cross != "否":
            print("::error::未检测到跨包越界改动，合规问答应填写“否”。")
            return 1

    print("路径与合规问答检查通过。")
    return 0


if __name__ == "__main__":
    sys.exit(main())

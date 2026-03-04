from __future__ import annotations

import json
from pathlib import Path

from agentlib.patch_executor import RollbackManager
from agent_kernel.schemas import Task
from agentlib.runtime_engine import RuntimeEngine


def _mk_task(*, task_id: str, payload: dict) -> Task:
    return Task(
        task_id=task_id,
        kind="code_task",
        description="selfdrive codex execution test",
        input_payload=dict(payload),
        status="ready",
    )


def test_selfdrive_codex_success_path_has_contract_and_changed_files(tmp_path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    engine = RuntimeEngine()
    audit_path = tmp_path / "selfdrive_api_audit.log"
    engine._selfdrive_api_audit_log_path = str(audit_path)

    target = tmp_path / "demo.py"
    target.write_text("print('ok')\n", encoding="utf-8")
    task = _mk_task(
        task_id="t_success",
        payload={
            "target_path": str(target),
            "instruction": "append one harmless line",
            "patch_ops": [{"op": "append_file", "path": str(target), "content": "# patched by txn\n"}],
        },
    )

    def _fake_delegate(**kwargs):
        return {
            "ok": True,
            "output": {
                "summary": "applied patch",
                "changed_files": [str(target)],
                "improvement_items": ["keep patch minimal"],
                "open_questions": [],
                "execution_contract": {
                    "proposed_action": "append one harmless line",
                    "assumed_preconditions": ["workspace_access", "tool_available:code_task"],
                    "expected_artifacts": [str(target)],
                    "self_check_plan": ["run minimal verify"],
                    "rollback_hint": "restore from pre-snapshot if verify fails",
                },
                "patch_ops": [{"op": "append_file", "path": str(target), "content": "# patched by txn\n"}],
            },
            "error": "",
            "wait_user": False,
            "artifacts": [f"artifact::{task.task_id}"],
        }

    engine.codex_delegate.try_chat_json = _fake_delegate
    out = engine._codex_execute_for_selfdrive(task=task)

    assert out["ok"] is True
    output = dict(out.get("output") or {})
    assert isinstance(output.get("changed_files"), list)
    assert str(output.get("summary") or "").strip()
    assert target.read_text(encoding="utf-8").endswith("# patched by txn\n")
    contract = dict(output.get("execution_contract") or {})
    assert str(contract.get("rollback_hint") or "").strip()
    assert isinstance(output.get("pre_snapshot"), list)
    assert isinstance(output.get("post_snapshot"), list)
    verify = dict(output.get("verify_evidence") or {})
    assert verify.get("ok") is True
    rollback = dict(output.get("rollback_result") or {})
    assert rollback.get("triggered") is False
    assert str(output.get("error_signature") or "") == ""

    assert audit_path.exists()
    rows = [json.loads(x) for x in audit_path.read_text(encoding="utf-8").splitlines() if x.strip()]
    assert rows
    last = dict(rows[-1] or {})
    assert str(last.get("task_id") or "") == "t_success"
    assert "latency_ms" in last


def test_selfdrive_codex_rejects_target_path_outside_workspace(tmp_path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    engine = RuntimeEngine()
    engine._selfdrive_api_audit_log_path = str(tmp_path / "selfdrive_api_audit.log")

    outside = (tmp_path.parent / "outside_forbidden.py").resolve()
    task = _mk_task(
        task_id="t_outside",
        payload={
            "target_path": str(outside),
            "instruction": "attempt forbidden write",
        },
    )
    out = engine._codex_execute_for_selfdrive(task=task)

    assert out["ok"] is False
    assert "permission_denied:target_path_outside_workspace" in str(out.get("error") or "")


def test_verify_failure_triggers_rollback_and_restores_file(tmp_path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    target = tmp_path / "mvp_target.py"
    original = "value = 1\n"
    target.write_text(original, encoding="utf-8")

    engine = RuntimeEngine()
    engine._selfdrive_api_audit_log_path = str(tmp_path / "selfdrive_api_audit.log")
    task = _mk_task(
        task_id="t_verify_fail",
        payload={
            "target_path": str(target),
            "instruction": "introduce syntax error then verify",
            "patch_ops": [{"op": "replace_file", "path": str(target), "content": "value =\n"}],
            "verify_command": "py -c \"import py_compile; py_compile.compile('mvp_target.py', doraise=True)\"",
        },
    )

    def _fake_delegate(**kwargs):
        return {
            "ok": True,
            "output": {
                "summary": "patch proposed",
                "changed_files": [str(target)],
                "improvement_items": [],
                "open_questions": [],
                "execution_contract": {
                    "proposed_action": "replace file",
                    "assumed_preconditions": ["workspace_access"],
                    "expected_artifacts": [str(target)],
                    "self_check_plan": ["run py_compile"],
                    "rollback_hint": "restore file from snapshot",
                },
                "patch_ops": [{"op": "replace_file", "path": str(target), "content": "value =\n"}],
            },
            "error": "",
            "wait_user": False,
            "artifacts": [],
        }

    engine.codex_delegate.try_chat_json = _fake_delegate
    out = engine._codex_execute_for_selfdrive(task=task)

    assert out["ok"] is False
    assert "verify_failed" in str(out.get("error") or "")
    output = dict(out.get("output") or {})
    verify = dict(output.get("verify_evidence") or {})
    assert verify.get("ok") is False
    rollback = dict(output.get("rollback_result") or {})
    assert rollback.get("ok") is True
    assert rollback.get("triggered") is True
    assert target.read_text(encoding="utf-8") == original


def test_rollback_idempotent_does_not_corrupt_state(tmp_path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    target = tmp_path / "idempotent.py"
    original = "x = 1\n"
    target.write_text(original, encoding="utf-8")

    mgr = RollbackManager(str(tmp_path))
    snap = mgr.capture([str(target)])
    target.write_text("x = 2\n", encoding="utf-8")
    first = mgr.rollback(snap)
    second = mgr.rollback(snap)
    assert first.get("ok") is True
    assert second.get("ok") is True
    assert target.read_text(encoding="utf-8") == original

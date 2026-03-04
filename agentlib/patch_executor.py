from __future__ import annotations

import base64
import hashlib
import os
import py_compile
import subprocess
import time
from pathlib import Path
from typing import Any, Dict, List, Optional


def _sha256_bytes(data: bytes) -> str:
    h = hashlib.sha256()
    h.update(data)
    return h.hexdigest()


def _norm_error_signature(prefix: str, message: str) -> str:
    p = str(prefix or "execution_error").strip().lower() or "execution_error"
    m = str(message or "").strip()
    return f"{p}:{m}" if m else p


def _resolve_under_workspace(path_text: str, workspace_root: str) -> Path:
    ws = Path(str(workspace_root or ".")).resolve()
    p = Path(str(path_text or "").strip())
    if not p.is_absolute():
        p = (ws / p).resolve()
    else:
        p = p.resolve()
    try:
        p.relative_to(ws)
    except Exception as exc:
        raise ValueError(f"path_outside_workspace:{p}") from exc
    return p


def _snapshot_public(path: str, item: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "path": str(path),
        "exists": bool(item.get("exists", False)),
        "size": int(item.get("size", 0) or 0),
        "sha256": str(item.get("sha256") or ""),
    }


class RollbackManager:
    def __init__(self, workspace_root: str):
        self.workspace_root = str(workspace_root or os.getcwd())

    def capture(self, paths: List[str]) -> Dict[str, Dict[str, Any]]:
        out: Dict[str, Dict[str, Any]] = {}
        for raw in list(paths or []):
            p = _resolve_under_workspace(raw, self.workspace_root)
            if p.exists():
                data = p.read_bytes()
                out[str(p)] = {
                    "path": str(p),
                    "exists": True,
                    "size": int(len(data)),
                    "sha256": _sha256_bytes(data),
                    "content_b64": base64.b64encode(data).decode("ascii"),
                }
            else:
                out[str(p)] = {
                    "path": str(p),
                    "exists": False,
                    "size": 0,
                    "sha256": "",
                    "content_b64": "",
                }
        return out

    def rollback(self, snapshot: Dict[str, Dict[str, Any]]) -> Dict[str, Any]:
        applied: List[str] = []
        errors: List[str] = []
        for path, item in dict(snapshot or {}).items():
            try:
                p = _resolve_under_workspace(path, self.workspace_root)
                should_exist = bool(item.get("exists", False))
                if not should_exist:
                    if p.exists():
                        p.unlink()
                    applied.append(str(p))
                    continue
                b64 = str(item.get("content_b64") or "")
                payload = base64.b64decode(b64.encode("ascii")) if b64 else b""
                p.parent.mkdir(parents=True, exist_ok=True)
                p.write_bytes(payload)
                applied.append(str(p))
            except Exception as exc:
                errors.append(f"{path}:{type(exc).__name__}:{exc}")
        return {
            "triggered": True,
            "ok": len(errors) == 0,
            "applied_files": applied,
            "errors": errors,
            "count": len(applied),
        }


class PatchExecutor:
    def __init__(self, workspace_root: str):
        self.workspace_root = str(workspace_root or os.getcwd())

    def apply(self, patch_ops: List[Dict[str, Any]]) -> Dict[str, Any]:
        changed: List[str] = []
        applied_ops: List[str] = []
        for idx, op in enumerate(list(patch_ops or []), start=1):
            if not isinstance(op, dict):
                return {
                    "ok": False,
                    "changed_files": changed,
                    "applied_ops": applied_ops,
                    "error_signature": _norm_error_signature("parse_error", f"patch_op_not_object_at_{idx}"),
                }
            kind = str(op.get("op") or "").strip().lower()
            target = str(op.get("path") or op.get("target_path") or op.get("file_path") or "").strip()
            if not kind or not target:
                return {
                    "ok": False,
                    "changed_files": changed,
                    "applied_ops": applied_ops,
                    "error_signature": _norm_error_signature("parse_error", f"patch_op_missing_fields_at_{idx}"),
                }
            try:
                p = _resolve_under_workspace(target, self.workspace_root)
            except Exception as exc:
                return {
                    "ok": False,
                    "changed_files": changed,
                    "applied_ops": applied_ops,
                    "error_signature": _norm_error_signature("permission_denied", str(exc)),
                }

            try:
                if kind in {"replace_file", "write_file"}:
                    content = str(op.get("content") or op.get("text") or "")
                    p.parent.mkdir(parents=True, exist_ok=True)
                    p.write_text(content, encoding="utf-8")
                elif kind == "append_file":
                    content = str(op.get("content") or op.get("text") or "")
                    p.parent.mkdir(parents=True, exist_ok=True)
                    with p.open("a", encoding="utf-8") as f:
                        f.write(content)
                elif kind == "delete_file":
                    if p.exists():
                        p.unlink()
                else:
                    return {
                        "ok": False,
                        "changed_files": changed,
                        "applied_ops": applied_ops,
                        "error_signature": _norm_error_signature("parse_error", f"unsupported_patch_op:{kind}"),
                    }
                changed.append(str(p))
                applied_ops.append(kind)
            except Exception as exc:
                return {
                    "ok": False,
                    "changed_files": changed,
                    "applied_ops": applied_ops,
                    "error_signature": _norm_error_signature("execution_error", f"{type(exc).__name__}:{exc}"),
                }

        uniq = []
        seen = set()
        for p in changed:
            if p in seen:
                continue
            seen.add(p)
            uniq.append(p)
        return {"ok": True, "changed_files": uniq, "applied_ops": applied_ops, "error_signature": ""}


class PatchExecutionTransaction:
    def __init__(self, workspace_root: Optional[str] = None, verify_timeout_sec: float = 120.0):
        self.workspace_root = str(workspace_root or os.getcwd())
        self.verify_timeout_sec = float(max(1.0, verify_timeout_sec))
        self.rollback_mgr = RollbackManager(self.workspace_root)
        self.executor = PatchExecutor(self.workspace_root)

    def run(
        self,
        *,
        task_id: str,
        input_payload: Dict[str, Any],
        execution_contract: Dict[str, Any],
        patch_ops: Optional[List[Dict[str, Any]]] = None,
        changed_files_hint: Optional[List[str]] = None,
        verify_command: str = "",
        audit_log_path: str = "",
    ) -> Dict[str, Any]:
        t0 = time.time()
        payload = dict(input_payload or {})
        contract = dict(execution_contract or {})
        ops = patch_ops if isinstance(patch_ops, list) else list(payload.get("patch_ops") or [])
        changed_hint = [str(x) for x in list(changed_files_hint or []) if str(x).strip()]
        rollback_hint = str(contract.get("rollback_hint") or "").strip()

        touched: List[str] = []
        for op in list(ops or []):
            if isinstance(op, dict):
                p = str(op.get("path") or op.get("target_path") or op.get("file_path") or "").strip()
                if p:
                    touched.append(p)
        touched.extend(changed_hint)
        if not touched:
            return {
                "success": True,
                "task_id": str(task_id or ""),
                "changed_files": [],
                "pre_snapshot": [],
                "post_snapshot": [],
                "verify_evidence": {"ok": True, "mode": "skipped", "reason": "no_touched_files"},
                "rollback_result": {"triggered": False, "ok": True, "reason": "not_needed", "rollback_hint": rollback_hint},
                "error_signature": "",
                "audit_log_path": str(audit_log_path or ""),
                "duration_ms": int((time.time() - t0) * 1000),
            }

        abs_touched: List[str] = []
        for p in touched:
            try:
                abs_touched.append(str(_resolve_under_workspace(p, self.workspace_root)))
            except Exception as exc:
                return {
                    "success": False,
                    "task_id": str(task_id or ""),
                    "changed_files": [],
                    "pre_snapshot": [],
                    "post_snapshot": [],
                    "verify_evidence": {"ok": False, "mode": "prepare", "reason": str(exc)},
                    "rollback_result": {"triggered": False, "ok": False, "reason": "prepare_failed", "rollback_hint": rollback_hint},
                    "error_signature": _norm_error_signature("permission_denied", str(exc)),
                    "audit_log_path": str(audit_log_path or ""),
                    "duration_ms": int((time.time() - t0) * 1000),
                }

        pre = self.rollback_mgr.capture(abs_touched)
        apply_out = {"ok": True, "changed_files": abs_touched, "error_signature": "", "applied_ops": []}
        if ops:
            apply_out = self.executor.apply(list(ops))
            if not bool(apply_out.get("ok")):
                rb = self.rollback_mgr.rollback(pre)
                return {
                    "success": False,
                    "task_id": str(task_id or ""),
                    "changed_files": [str(x) for x in list(apply_out.get("changed_files") or [])],
                    "pre_snapshot": [_snapshot_public(k, v) for k, v in pre.items()],
                    "post_snapshot": [_snapshot_public(k, v) for k, v in self.rollback_mgr.capture(abs_touched).items()],
                    "verify_evidence": {"ok": False, "mode": "apply", "reason": "apply_failed"},
                    "rollback_result": dict(rb or {}),
                    "error_signature": str(apply_out.get("error_signature") or _norm_error_signature("execution_error", "apply_failed")),
                    "audit_log_path": str(audit_log_path or ""),
                    "duration_ms": int((time.time() - t0) * 1000),
                }

        changed_files = [str(x) for x in list(apply_out.get("changed_files") or []) if str(x).strip()]
        post = self.rollback_mgr.capture(abs_touched)
        verify_evidence = self._verify(
            changed_files=changed_files or abs_touched,
            verify_command=str(verify_command or payload.get("verify_command") or "").strip(),
        )
        if not bool(verify_evidence.get("ok")):
            rb = self.rollback_mgr.rollback(pre)
            err = _norm_error_signature("verify_failed", str(verify_evidence.get("reason") or "verification_failed"))
            return {
                "success": False,
                "task_id": str(task_id or ""),
                "changed_files": changed_files,
                "pre_snapshot": [_snapshot_public(k, v) for k, v in pre.items()],
                "post_snapshot": [_snapshot_public(k, v) for k, v in post.items()],
                "verify_evidence": verify_evidence,
                "rollback_result": dict(rb or {}),
                "error_signature": err,
                "audit_log_path": str(audit_log_path or ""),
                "duration_ms": int((time.time() - t0) * 1000),
            }

        return {
            "success": True,
            "task_id": str(task_id or ""),
            "changed_files": changed_files,
            "pre_snapshot": [_snapshot_public(k, v) for k, v in pre.items()],
            "post_snapshot": [_snapshot_public(k, v) for k, v in post.items()],
            "verify_evidence": verify_evidence,
            "rollback_result": {"triggered": False, "ok": True, "reason": "not_needed", "rollback_hint": rollback_hint},
            "error_signature": "",
            "audit_log_path": str(audit_log_path or ""),
            "duration_ms": int((time.time() - t0) * 1000),
        }

    def _verify(self, *, changed_files: List[str], verify_command: str) -> Dict[str, Any]:
        cmd = str(verify_command or "").strip()
        if cmd:
            try:
                cp = subprocess.run(
                    cmd,
                    cwd=self.workspace_root,
                    shell=True,
                    capture_output=True,
                    text=True,
                    timeout=self.verify_timeout_sec,
                )
                return {
                    "ok": int(cp.returncode) == 0,
                    "mode": "command",
                    "command": cmd,
                    "returncode": int(cp.returncode),
                    "stdout_tail": str(cp.stdout or "")[-1500:],
                    "stderr_tail": str(cp.stderr or "")[-1500:],
                    "reason": "" if int(cp.returncode) == 0 else f"command_exit_{int(cp.returncode)}",
                }
            except subprocess.TimeoutExpired:
                return {"ok": False, "mode": "command", "command": cmd, "reason": "verify_timeout"}
            except Exception as exc:
                return {"ok": False, "mode": "command", "command": cmd, "reason": f"{type(exc).__name__}:{exc}"}

        py_targets: List[str] = []
        for p in list(changed_files or []):
            path = Path(str(p))
            if path.suffix.lower() == ".py" and path.exists():
                py_targets.append(str(path))
        if not py_targets:
            return {"ok": True, "mode": "py_compile", "checked_files": [], "reason": "no_python_targets"}
        for p in py_targets:
            try:
                py_compile.compile(p, doraise=True)
            except Exception as exc:
                return {
                    "ok": False,
                    "mode": "py_compile",
                    "checked_files": py_targets,
                    "reason": f"{type(exc).__name__}:{exc}",
                }
        return {"ok": True, "mode": "py_compile", "checked_files": py_targets, "reason": ""}


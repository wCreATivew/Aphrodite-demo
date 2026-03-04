from __future__ import annotations

import argparse
import os
import runpy
import sys
import time
import traceback
from typing import TextIO


class _Tee:
    def __init__(self, stream: TextIO, log_fp: TextIO):
        self._stream = stream
        self._log_fp = log_fp

    def write(self, data: str) -> int:
        text = str(data)
        n = self._stream.write(text)
        try:
            self._log_fp.write(text)
        except Exception:
            pass
        return n

    def flush(self) -> None:
        try:
            self._stream.flush()
        except Exception:
            pass
        try:
            self._log_fp.flush()
        except Exception:
            pass


def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Run a Python script and tee stdout/stderr to log.")
    p.add_argument("--script", required=True, help="Target Python script path")
    p.add_argument("--log", default=os.path.join("monitor", "ide_debug.log"), help="Log output path")
    p.add_argument("script_args", nargs=argparse.REMAINDER, help="Arguments passed to target script")
    return p.parse_args()


def main() -> int:
    args = _parse_args()
    script = os.path.abspath(str(args.script))
    log_path = os.path.abspath(str(args.log))
    os.makedirs(os.path.dirname(log_path) or ".", exist_ok=True)
    os.environ.setdefault("PYTHONUTF8", "1")
    os.environ.setdefault("PYTHONIOENCODING", "utf-8")

    pass_args = list(args.script_args or [])
    if pass_args and pass_args[0] == "--":
        pass_args = pass_args[1:]

    with open(log_path, "a", encoding="utf-8", errors="ignore") as lf:
        lf.write(f"\n\n===== debug session {time.strftime('%Y-%m-%d %H:%M:%S')} =====\n")
        lf.write(f"script={script}\n")
        lf.flush()

        old_out, old_err = sys.stdout, sys.stderr
        try:
            if hasattr(old_out, "reconfigure"):
                old_out.reconfigure(encoding="utf-8", errors="replace")
            if hasattr(old_err, "reconfigure"):
                old_err.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass
        sys.stdout = _Tee(old_out, lf)  # type: ignore[assignment]
        sys.stderr = _Tee(old_err, lf)  # type: ignore[assignment]

        try:
            sys.argv = [script] + pass_args
            runpy.run_path(script, run_name="__main__")
            return 0
        except SystemExit as e:
            exit_code = getattr(e, "code", 0)
            code = int(exit_code if exit_code is not None else 0)
            return code
        except Exception:
            traceback.print_exc()
            return 1
        finally:
            try:
                sys.stdout.flush()
                sys.stderr.flush()
            except Exception:
                pass
            sys.stdout = old_out
            sys.stderr = old_err


if __name__ == "__main__":
    raise SystemExit(main())

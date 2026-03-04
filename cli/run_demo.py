from __future__ import annotations

import argparse
import json
import sys
import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

try:
    from engine_adapter import build_engine_adapter
except Exception:
    from cli.engine_adapter import build_engine_adapter


def _load_logging_helpers():
    try:
        from semantic_trigger.logging_utils import format_engine_result, result_to_dict

        return format_engine_result, result_to_dict
    except Exception:
        mod_path = SRC / "semantic_trigger" / "logging_utils.py"
        spec = importlib.util.spec_from_file_location("semantic_trigger_logging_utils_fallback", mod_path)
        if spec is None or spec.loader is None:
            raise RuntimeError(f"cannot load logging helpers: {mod_path}")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module.format_engine_result, module.result_to_dict


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Semantic trigger single-query demo")
    parser.add_argument("--query", required=True, help="User query")
    parser.add_argument("--debug", action="store_true", help="Print full debug block")
    parser.add_argument("--top-k", type=int, default=5, help="Top-K candidates")
    parser.add_argument("--triggers-path", default="", help="Path to trigger definitions")
    parser.add_argument("--json", action="store_true", help="Print JSON output")
    parser.add_argument("--force-stub", action="store_true", help="Force stub backend")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    format_engine_result, result_to_dict = _load_logging_helpers()
    adapter = build_engine_adapter(triggers_path=args.triggers_path, prefer_real=not args.force_stub)
    raw = adapter.infer(args.query, top_k=max(1, int(args.top_k)))
    result = result_to_dict(raw)

    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0

    print(format_engine_result(result, debug=args.debug))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

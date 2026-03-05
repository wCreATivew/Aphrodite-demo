from pathlib import Path
import importlib.util


MODULE_PATH = Path(__file__).resolve().parents[2] / "scripts" / "eval_router.py"
spec = importlib.util.spec_from_file_location("eval_router", MODULE_PATH)
mod = importlib.util.module_from_spec(spec)
assert spec and spec.loader
spec.loader.exec_module(mod)


_binary_f1 = mod._binary_f1
_macro_f1 = mod._macro_f1
_normalize_scope = mod._normalize_scope


def test_normalize_scope_accepts_multi_scope():
    assert _normalize_scope(["MAIN", "PROJECT_ONLY"]) == ["MAIN", "PROJECT_ONLY"]
    assert _normalize_scope("MAIN") == ["MAIN"]


def test_binary_f1_basic():
    assert _binary_f1(tp=2, fp=0, fn=0) == 1.0
    assert _binary_f1(tp=0, fp=1, fn=1) == 0.0


def test_macro_f1_computes_multi_class_average():
    confusion = {
        "A": {"A": 2, "B": 1},
        "B": {"A": 1, "B": 2},
    }
    assert round(_macro_f1(confusion), 4) == 0.6667

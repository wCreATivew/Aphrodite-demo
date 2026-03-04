from __future__ import annotations
import sys
import os
import types
import json
import inspect
import traceback
from importlib.machinery import SourceFileLoader

TARGET_DEFAULT = r"c:\Users\CreATive\Desktop\agent\A0.32026205.01.py"


def _ensure_stub_modules():
    def add_module(name: str, mod: types.ModuleType) -> None:
        if name not in sys.modules:
            sys.modules[name] = mod

    # numpy stub
    try:
        import numpy  # noqa: F401
    except Exception:
        np_mod = types.ModuleType("numpy")
        class _Linalg:
            @staticmethod
            def norm(x):
                try:
                    return sum(v * v for v in x) ** 0.5
                except Exception:
                    return 0.0
        def _to_list(x):
            return x if isinstance(x, list) else [x]
        def exp(x):
            import math
            xs = _to_list(x)
            return [math.exp(v) for v in xs]
        def max_(x):
            xs = _to_list(x)
            return max(xs) if xs else 0.0
        def sum_(x):
            xs = _to_list(x)
            return sum(xs)
        def zeros(shape, dtype=None):
            if isinstance(shape, tuple) and len(shape) == 2:
                return [[0.0] * shape[1] for _ in range(shape[0])]
            if isinstance(shape, int):
                return [0.0] * shape
            return []
        def array(x, dtype=None):
            return x
        np_mod.exp = exp
        np_mod.max = max_
        np_mod.sum = sum_
        np_mod.zeros = zeros
        np_mod.array = array
        np_mod.float32 = float
        np_mod.int64 = int
        np_mod.linalg = _Linalg()
        add_module("numpy", np_mod)

    # openai stub
    try:
        import openai  # noqa: F401
    except Exception:
        openai_mod = types.ModuleType("openai")
        class BadRequestError(Exception):
            pass
        openai_mod.BadRequestError = BadRequestError
        add_module("openai", openai_mod)
        # openai.OpenAI
        class OpenAI:
            def __init__(self, *args, **kwargs):
                pass
        openai_mod.OpenAI = OpenAI
        add_module("openai", openai_mod)

    # sentence_transformers stub
    try:
        import sentence_transformers  # noqa: F401
    except Exception:
        st_mod = types.ModuleType("sentence_transformers")
        class SentenceTransformer:
            def __init__(self, *args, **kwargs):
                self._dim = 384
            def get_sentence_embedding_dimension(self):
                return self._dim
            def encode(self, texts, **kwargs):
                # return zeros
                if isinstance(texts, list):
                    return [[0.0] * self._dim for _ in texts]
                return [0.0] * self._dim
        st_mod.SentenceTransformer = SentenceTransformer
        add_module("sentence_transformers", st_mod)

    # faiss stub
    try:
        import faiss  # noqa: F401
    except Exception:
        faiss_mod = types.ModuleType("faiss")
        class _IndexFlatIP:
            def __init__(self, dim):
                self.dim = dim
                self.ntotal = 0
            def add(self, x):
                try:
                    self.ntotal += len(x)
                except Exception:
                    self.ntotal += 1
            def search(self, x, k):
                # return zeros
                import numpy as np
                if hasattr(x, "shape"):
                    n = x.shape[0]
                else:
                    n = 1
                return (np.zeros((n, k), dtype="float32"), np.zeros((n, k), dtype="int64"))
        def normalize_L2(x):
            return x
        def write_index(index, path):
            return None
        def read_index(path):
            return _IndexFlatIP(384)
        faiss_mod.IndexFlatIP = _IndexFlatIP
        faiss_mod.normalize_L2 = normalize_L2
        faiss_mod.write_index = write_index
        faiss_mod.read_index = read_index
        add_module("faiss", faiss_mod)

    # PIL stub
    try:
        from PIL import Image  # noqa: F401
    except Exception:
        pil_mod = types.ModuleType("PIL")
        pil_img_mod = types.ModuleType("PIL.Image")
        class _Image:
            @staticmethod
            def open(path):
                raise RuntimeError("PIL not available")
        pil_img_mod.Image = _Image
        pil_mod.Image = _Image
        add_module("PIL", pil_mod)
        add_module("PIL.Image", pil_img_mod)

    # prompt_toolkit stub
    try:
        import prompt_toolkit  # noqa: F401
    except Exception:
        pt_mod = types.ModuleType("prompt_toolkit")
        class PromptSession:
            def __init__(self, *args, **kwargs):
                pass
        pt_mod.PromptSession = PromptSession
        add_module("prompt_toolkit", pt_mod)

        pt_patch = types.ModuleType("prompt_toolkit.patch_stdout")
        class _Patch:
            def __enter__(self):
                return self
            def __exit__(self, exc_type, exc, tb):
                return False
        def patch_stdout(*args, **kwargs):
            return _Patch()
        pt_patch.patch_stdout = patch_stdout
        add_module("prompt_toolkit.patch_stdout", pt_patch)

        pt_kb = types.ModuleType("prompt_toolkit.key_binding")
        class KeyBindings:
            def __init__(self):
                pass
        pt_kb.KeyBindings = KeyBindings
        add_module("prompt_toolkit.key_binding", pt_kb)

        pt_keys = types.ModuleType("prompt_toolkit.keys")
        class Keys:
            ControlC = "ControlC"
            ControlD = "ControlD"
        pt_keys.Keys = Keys
        add_module("prompt_toolkit.keys", pt_keys)


def _load_target(path: str):
    loader = SourceFileLoader("target_module", path)
    mod = types.ModuleType(loader.name)
    mod.__file__ = path
    sys.modules[loader.name] = mod
    loader.exec_module(mod)
    return mod


def _patch_llm(mod):
    class _DummyMsg:
        def __init__(self, content: str):
            self.content = content
    class _DummyChoice:
        def __init__(self, content: str):
            self.message = _DummyMsg(content)
    class _DummyResp:
        def __init__(self, content: str):
            self.choices = [_DummyChoice(content)]

    def _make_json_reply():
        obj = {
            "reply": "测试回复",
            "emotion": "calm",
            "action": "suggest",
            "memory": [],
            "state_update": {"energy": 60, "affinity": 20, "topic": "test"},
            "judgments": [
                {"claim": "这是测试回答", "uncertainty": 0.3, "basis": "inference"}
            ],
            "uncertainty_mode": "normal",
        }
        return json.dumps(obj, ensure_ascii=False)

    def chat_create_safe(**kwargs):
        return _DummyResp(_make_json_reply())

    mod.chat_create_safe = chat_create_safe


def _reset_state(mod):
    mod.summary = "测试摘要"
    mod.state = {
        "emotion": "calm",
        "energy": 60,
        "affinity": 20,
        "topic": "smalltalk",
        "topic_prev": None,
        "breaker_active": False,
        "breaker_tag": None,
        "breaker_since_ts": None,
        "last_dom_tag": None,
        "last_dom_weight": 0.0,
        "last_dom_ts": 0.0,
        "last_turn_ts": None,
        "session_start_ts": None,
        "last_nudge_ts": 0.0,
        "nudge_count": 0,
        "idle_pressure": 0,
        "idle_stage": 0,
        "last_user_ts": 0.0,
        "input_epoch": 0,
    }
    mod.recent_messages = []
    mod.long_term_memory = []
    mod.memory_store = None

def _has_real_memory_deps():
    try:
        import numpy  # noqa: F401
        import faiss  # noqa: F401
        import sentence_transformers  # noqa: F401
        return True
    except Exception:
        return False


def _run_memory_real(mod):
    import os
    import time as _time
    base_dir = os.path.join(os.getcwd(), "healthcheck_tmp")
    os.makedirs(base_dir, exist_ok=True)
    stamp = str(int(_time.time()))
    db_path = os.path.join(base_dir, f"memory_{stamp}.sqlite")
    index_path = os.path.join(base_dir, f"memory_{stamp}.faiss")
    ids_path = os.path.join(base_dir, f"memory_{stamp}.npy")
    ms = mod.MemoryStore(db_path=db_path, index_path=index_path, ids_path=ids_path, model_name="BAAI/bge-small-zh-v1.5", device="cpu")
    ms.add_many(["?????", "??????", "??????"])
    got = ms.retrieve("??", k=3)
    if not isinstance(got, list) or not got:
        raise RuntimeError("memory retrieve returned empty")
    return {"count": ms.count(), "retrieve": got}



def _run_case(name, fn, *args, **kwargs):
    try:
        result = fn(*args, **kwargs)
        return True, result, None
    except Exception as e:
        return False, None, traceback.format_exc()


def main():
    args = sys.argv[1:]
    memory_real = False
    if "--memory-real" in args:
        memory_real = True
        args = [a for a in args if a != "--memory-real"]
    target = TARGET_DEFAULT
    if args:
        target = args[0]
    if not os.path.exists(target):
        print("[FATAL] target not found:", target)
        sys.exit(2)

    _ensure_stub_modules()
    mod = _load_target(target)
    _patch_llm(mod)
    _reset_state(mod)

    results = []

    # Core parsing and utils
    results.append(("parse_json_strict_ok", *_run_case("parse_json_strict_ok", mod.parse_json_strict, '{"a":1}')))
    results.append(("parse_json_strict_bad", *_run_case("parse_json_strict_bad", mod.parse_json_strict, 'bad {"a":1}')))
    results.append(("clip_int", *_run_case("clip_int", mod.clip_int, "9", 0, 10, 0)))

    # Prompt logic
    results.append(("is_eval_question", *_run_case("is_eval_question", mod.is_eval_question, "这好用吗")))
    results.append(("has_example_marker", *_run_case("has_example_marker", mod.has_example_marker, "比如这样")))
    results.append(("example_is_constraint", *_run_case("example_is_constraint", mod.example_is_constraint, "必须按这个例子")))

    # Build messages (no memory)
    results.append(("build_messages", *_run_case("build_messages", mod.build_messages, "你好", None, None)))

    # Summarize (uses patched llm)
    results.append(("summarize", *_run_case("summarize", mod.summarize, "旧摘要", [{"role": "user", "content": "hi"}])))

    # Model update path
    fake_data = {
        "reply": "这是回复",
        "emotion": "calm",
        "action": "suggest",
        "memory": [],
        "state_update": {"energy": 55, "affinity": 22, "topic": "test"},
        "judgments": [{"claim": "测试判断", "uncertainty": 0.2, "basis": "inference"}],
        "uncertainty_mode": "normal",
    }
    results.append(("update_from_model", *_run_case("update_from_model", mod.update_from_model, "你好", fake_data)))

    # Consistency + critic pipeline
    msgs, _ = mod.build_messages("你好", None, None)
    results.append(("_generate_model_data", *_run_case("_generate_model_data", mod._generate_model_data, msgs, "你好", True)))
    results.append(("_run_critic", *_run_case("_run_critic", mod._run_critic, "你好", fake_data)))

    # DB tables (local sqlite)
    results.append(("ensure_chat_tables_backend", *_run_case("ensure_chat_tables_backend", mod.ensure_chat_tables_backend)))


    if memory_real:
        if _has_real_memory_deps():
            results.append(("memory_store_real", *_run_case("memory_store_real", _run_memory_real, mod)))
        else:
            results.append(("memory_store_real", False, None, "missing deps: numpy/faiss/sentence_transformers"))

    # Report
    ok = 0
    fail = 0
    print("\n=== Health Check Report ===")
    for name, passed, out, err in results:
        if passed:
            ok += 1
            print(f"[OK]   {name}")
        else:
            fail += 1
            print(f"[FAIL] {name}\n{err}")

    # Function inventory
    funcs = [
        (n, f) for n, f in inspect.getmembers(mod, inspect.isfunction)
        if getattr(f, "__module__", None) == mod.__name__
    ]
    tested = set(r[0] for r in results)
    skipped = [n for n, _ in funcs if n not in tested]
    print("\nTested:", len(tested), "functions")
    print("Skipped:", len(skipped), "functions")
    if skipped:
        print("Skipped list (manual/unsafe):")
        for n in sorted(skipped):
            print("-", n)

    if fail:
        sys.exit(1)


if __name__ == "__main__":
    main()

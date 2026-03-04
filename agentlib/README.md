# agentlib 模块说明

本目录包含从主程序中拆出的可复用“认知与调度”组件，供其他工具或脚本直接 import 使用。

## 顶层模块

- `metrics.py`
  - 指标采样与 SQLite 写入（用于监控曲线/延迟等）。

- `learned_lists.py`
  - 可学习词表与状态聚合（fillers / pos_words / neg_words / stop_chars 等）。

- `style_policy.py`
  - 自学习风格策略（REINFORCE + 轻量特征）。
  - 入口：`SelfLearningStylePolicy`、`infer_reward_from_user_text`。

- `memory_store.py`
  - 长期记忆（SQLite + FAISS + SentenceTransformer）。
  - 包含记忆门控、短语抽取、再排序等逻辑。

- `web_search.py`
  - 轻量联网搜索（可选，默认关闭）。

- `goal_stack.py`
  - 目标栈（当前目标/优先级/完成标记）。

- `tool_router.py`
  - 简单工具路由（保守策略）。

- `memory_arbiter.py`
  - 记忆仲裁（当前目标 + 记忆切片）。

## 调度内核（sched_core）

- `sched_core/task_queue.py`
  - SQLite 任务队列（落盘、可恢复）。

- `sched_core/tool_executor.py`
  - 工具执行器（注册/统一调用接口）。

- `sched_core/memory_governance.py`
  - 记忆治理（短期/任务/长期/工具分层）。

## 快速使用示例

```python
from agentlib import (
    MemoryStore, PhraseFilter, init_learned_lists, refresh_state,
    TaskQueue, ToolExecutor, MemoryGovernance
)

# 1) 记忆系统
ll = init_learned_lists("learned_lists.json")
state = refresh_state(ll)
store = MemoryStore(phrase_filter=PhraseFilter.from_state(state))
store.add_many(["用户喜欢轻松语气", "用户过敏花粉"])
print(store.retrieve("过敏", k=3))

# 2) 任务队列（落盘）
tasks = TaskQueue("monitor/tasks.db")
tid = tasks.add("整理会议纪要", priority=2)
print(tasks.next())

# 3) 工具执行器
exec = ToolExecutor()
exec.register("echo", lambda q: f"echo: {q}")
print(exec.run("echo", "hello"))

# 4) 记忆治理
gov = MemoryGovernance()
```

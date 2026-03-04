# Companion 记忆/RAG 关系索引

该文件用于快速查看当前陪伴框架的跨文件关系。

## 主运行链路
1. `Aphrodite demo ver.A.py`
2. `agentlib/companion_chat.py:companion_prepare_messages`
3. `agentlib/companion_rag.py:retrieve_memory_context`（长期记忆召回）
4. `agentlib/companion_rag.py:build_rag_package`
5. `agentlib/companion_chat.py:build_companion_messages`
6. `agentlib/glm_client.py:GLMClient.stream_chat`
7. `agentlib/companion_rag.py:record_turn_memory`（回合写回）

## 文件职责
- `agentlib/companion_prompt.py`
  - 定义提示词分段（`persona/style/safety/response_rules`）
  - 渲染 system prompt 文本

- `agentlib/companion_rag.py`
  - 检索管线与诊断信息输出
  - 实现：
    - self-rag 决策门
    - query variants
    - keyword/embedding/hybrid 召回
    - corrective 过滤
    - diversity 筛选
  - 输出 `RagResult` 供运行与调试使用

- `agentlib/companion_rag.py`（已融合 memory bridge）
  - 除了检索管线外，还包含长期记忆桥接能力：
    - `retrieve_memory_context`（读）
    - `record_turn_memory`（写）
    - `get_memory_store/get_memory_status`（存储状态）

- `agentlib/companion_chat.py`
  - 组装 OpenAI 兼容消息结构
  - 将 RAG 输出拼接到 system prompt
  - 对外提供：
    - `companion_reply_stream`（运行时）
    - `companion_prepare_messages`（调试与观测）

- `agentlib/glm_client.py`
  - 模型提供方路由（`openai_compat` / `zhipuai`）
  - 重试、异常封装、流式输出

## 调试入口
- 检索 trace 文本：
  - `agentlib/companion_rag.py:render_rag_trace`
- System prompt + 检索上下文可视化：
  - `Aphrodite demo ver.A.py:build_debug_prompt_and_rag`

## 记忆能力范围说明
- 当前 `companion_rag.py` 主要负责“给定知识列表”的检索与筛选。
- 它还没有完整覆盖“长期记忆写回 + 冲突治理 + 遗忘强化”的全生命周期。
- 如果需要完整记忆治理，需要继续整合暂停项目中更重的记忆存储逻辑。

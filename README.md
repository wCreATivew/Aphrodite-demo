# Aphrodite-demo（Demo 完成版说明）

Aphrodite-demo 现在的定位是：**具身类 Agent Demo 底盘**，目标不是单点聊天，而是形成可扩展的「感知 → 决策 → 动作 → 场景反馈」闭环。

---

## 1. 当前 Demo 的核心目标

本项目围绕 5 个能力建设：

1. **核心 Brain**：统一决策中枢（融合输入、生成动作计划、输出执行指令）
2. **可操控外壳（Shell）**：Agent 可以操作“身体”或执行器
3. **可互动场景（Scene）**：环境状态可被动作改变，并反向影响决策
4. **核心感知能力（Pseudo Senses）**：伪视觉、伪听觉、伪触觉、伪嗅觉
5. **对外输出能力（Actuation）**：对话、交互、场景影响

> 说明：`src/semantic_trigger/` 属于历史路径，当前不作为主线。

---

## 2. 架构总览（当前可运行骨架）

```text
Perception Adapters (vision/audio/tactile/olfactory)
        ↓
Perception Fusion
        ↓
Brain / Orchestrator (plan → execute → evaluate → reflect)
        ↓
Actuation (dialogue / interaction / scene effects)
        ↓
Scene Runtime & State Store
        ↺ (feedback loop)
```

---

## 3. 目录速览（与 Demo 主线相关）

- `agentlib/autonomy/`
  - `orchestrator.py`：任务循环编排
  - `models.py`：核心数据模型
  - `interfaces.py`：Planner/Executor/Evaluator/Reflector 接口
  - `state.py` / `store.py`：状态与存储
  - `scene_runtime.py`：场景运行层
  - `perception/`：伪视觉/听觉/触觉/嗅觉与融合
  - `actuation/`：对话、交互、场景影响执行器
  - `shell_adapters/`：外壳适配器（含 mock）
  - `demo_mvp.py` / `demo_v2.py`：演示入口

- `agentlib/runtime_engine.py`
  - 综合运行时中枢（历史能力与当前能力共存）

- `rag_offline/`
  - 离线数据构建、检索评估、参数调优、回放工具

---

## 4. 环境要求

- Python 3.10+
- 建议使用虚拟环境

```bash
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

---

## 5. 快速运行 Demo

当前没有唯一“主入口”，推荐以下两种演示方式：

### A. Orchestrator MVP 演示

```bash
python -m agentlib.autonomy.demo_mvp
```

你将看到：
- 任务被计划并执行
- 失败任务触发 fallback/retry
- 最终 summary 与任务状态输出

### B. Orchestrator V2 演示（更接近真实流程）

```bash
python -m agentlib.autonomy.demo_v2
```

你将看到：
- 多任务执行（含权限失败、超时重试等）
- 评估与反思（evaluate / reflect）
- 状态、任务列表、执行结果汇总

## 6. 常见问题

### Q1：为什么没有统一入口？
A：当前是多模态耦合阶段，采用事件驱动与演示入口并行，后续再收敛为统一启动器。

### Q2：语义触发模块还用吗？
A：目前不作为主链路，默认按历史遗留处理。

### Q3：情感算法文件缺失怎么办？
A：先保留接口位，不阻塞主循环；文件补齐后再接入。

---

## 10. 后续路线

- 第二轮：稳定性、冲突裁决、执行可靠性、场景一致性
- 第三轮：策略增强、情感算法接入、演示产品化


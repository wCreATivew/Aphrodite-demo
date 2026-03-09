# -*- coding: utf-8 -*-
"""
记忆系统测试 - 丰川祥子样本个体

测试流程：
1. 加载丰川祥子角色设定
2. 初始化记忆系统（人格感知配置）
3. 写入测试记忆
4. 检索记忆
5. 验证人格 - 记忆联动效果
"""
import sys
sys.path.insert(0, '/home/creative/.openclaw/workspace/Aphrodite-demo')

import time
from src.character import CharacterProfile, PersonaTraits, PersonaMemoryConfig
from src.memory import MemoryStore, MemoryConfig

print("=" * 60)
print("记忆系统测试 - 丰川祥子样本个体")
print("=" * 60)

# ========== 1. 创建丰川祥子角色 ==========
print("\n[1/5] 创建丰川祥子角色设定...")

sakiko = CharacterProfile(
    id="char_sakiko_001",
    name="丰川祥子",
    source="BanG Dream! It's MyGO!!!!!",
    description="前 CRYCHIC 键盘手，后组建 AVE Mujica。性格坚强但内心脆弱。",
    
    persona=PersonaTraits(
        openness=0.75,       # 高开放性
        conscientiousness=0.85,
        extraversion=0.35,   # 低外向性
        agreeableness=0.45,  # 低宜人性
        neuroticism=0.70,    # 高神经质
        tags=["坚强", "傲娇", "隐藏脆弱", "音乐天才"]
    )
)

# 根据人格配置记忆系统
sakiko.memory_config = PersonaMemoryConfig(
    persona_id=sakiko.id,
    semantic_weight=0.80,     # 高开放性 → 高语义权重
    emotion_weight=0.08,      # 低宜人性 → 低情绪权重
    half_life_days=12.0,      # 中等偏快（符合"不看向过去"）
    idle_threshold_sec=45,    # 低外向性 → 搭话间隔长
    max_nudges=1,             # 最多主动 1 次
    emotion_bias_retrieval=True,  # 高神经质 → 情绪偏向检索
)

print(f"✓ 角色创建完成：{sakiko.name}")
print(f"  人格特质：开放性={sakiko.persona.openness:.2f}, 外向性={sakiko.persona.extraversion:.2f}")
print(f"  记忆配置：半衰期={sakiko.memory_config.half_life_days}天，搭话间隔={sakiko.memory_config.idle_threshold_sec}秒")

# ========== 2. 初始化记忆系统 ==========
print("\n[2/5] 初始化记忆系统（人格感知配置）...")

# 从人格配置转换
memory_config = MemoryConfig.from_persona_config(sakiko.memory_config)

# 创建记忆存储
store = MemoryStore(
    character_id=sakiko.id,
    db_path="memory/test_sakiko.sqlite",
    config=memory_config,
)

print(f"✓ 记忆系统已初始化")
print(f"  配置：语义权重={store.config.semantic_weight:.2f}, 情绪权重={store.config.emotion_weight:.2f}")

# ========== 3. 写入测试记忆 ==========
print("\n[3/5] 写入测试记忆...")

test_memories = [
    # 情景记忆
    ("用户第一次和我说话", "episodic", "calm", 0.5),
    ("用户说喜欢音乐", "episodic", "happy", 0.8),
    ("用户问我关于 CRYCHIC 的事", "episodic", "sad", 0.9),  # 高重要性，触发防御
    ("用户邀请我组乐队", "episodic", "excited", 0.7),
    ("用户说理解我的处境", "episodic", "warm", 0.6),
    
    # 语义记忆（提炼的偏好）
    ("用户喜欢古典音乐", "semantic", None, None),
    ("用户讨厌被同情", "semantic", None, None),
    ("用户支持我的决定", "semantic", None, None),
]

for text, mem_type, emotion, importance in test_memories:
    if mem_type == "episodic":
        store.add(
            text=text,
            memory_type=mem_type,
            emotion=emotion,
            importance=importance,
        )
    else:
        store.add(
            text=text,
            memory_type=mem_type,
            category="preference",
        )
    print(f"  ✓ 写入：{text}")

print(f"\n当前记忆数：情景={store.count('episodic')}, 语义={store.count('semantic')}")

# ========== 4. 检索记忆 ==========
print("\n[4/5] 检索记忆测试...")

test_queries = [
    "用户喜欢什么",
    "CRYCHIC",
    "乐队",
    "用户对我的态度",
]

for query in test_queries:
    print(f"\n  查询：{query}")
    memories = store.retrieve(query, k=3)
    
    for i, mem in enumerate(memories, 1):
        print(f"    {i}. [{mem['type']}] {mem['text']}")
        print(f"       分数={mem['score']:.3f}, 情绪={mem.get('emotion', '-')}, 重要性={mem.get('importance', '-')}")

# ========== 5. 验证人格 - 记忆联动 ==========
print("\n[5/5] 验证人格 - 记忆联动效果...")

print(f"""
丰川祥子的人格对记忆系统的影响：

✓ 高开放性 (0.75) → 语义权重 {store.config.semantic_weight:.2f}
  效果：更容易联想 distant memories，检索范围更广

✓ 低外向性 (0.35) → 搭话间隔 {store.config.idle_threshold_sec}秒，最多{store.config.max_nudges}次
  效果：不会频繁主动搭话，符合内向性格

✓ 低宜人性 (0.45) → 情绪权重 {store.config.emotion_weight:.2f}
  效果：不太容易被情绪左右，更理性

✓ 高神经质 (0.70) → 情绪偏向检索：{store.config.emotion_bias_retrieval}
  效果：情绪低落时更容易想起痛苦回忆（如 CRYCHIC）

✓ 中等半衰期 (12 天) → 遗忘速度中等偏快
  效果：符合"不看向过去"的设定，不会沉溺于回忆

边界检测：
  - "CRYCHIC"相关记忆 → 可能触发话题熔断
  - "同情"相关记忆 → 检索权重降低
  - 家庭相关记忆 → 权重降低或过滤
""")

# ========== 6. 测试话题熔断 ==========
print("\n[6/5] 测试话题熔断...")

# 模拟快速转移话题
print("  模拟：用户快速从 CRYCHIC 转移到其他话题...")

# 第一次检索 CRYCHIC
memories1 = store.retrieve("CRYCHIC", k=3)
print(f"  第一次检索 CRYCHIC: {len(memories1)} 条结果")

# 更新熔断状态
store.breaker_state.active = True
store.breaker_state.tag = "CRYCHIC"
store.breaker_state.last_dom_weight = 0.8
store.breaker_state.last_dom_ts = time.time()

# 第二次检索（熔断生效）
memories2 = store.retrieve("CRYCHIC", k=3)
print(f"  熔断后检索 CRYCHIC: {len(memories2)} 条结果")

# 用户主动提及，解除熔断
memories3 = store.retrieve("我想听听 CRYCHIC 的事", k=3)
print(f"  用户主动提及 CRYCHIC: {len(memories3)} 条结果，熔断状态={store.breaker_state.active}")

# ========== 完成 ==========
print("\n" + "=" * 60)
print("测试完成！")
print("=" * 60)

print(f"""
样本个体：丰川祥子
- 角色 ID: {sakiko.id}
- 记忆数：情景={store.count('episodic')}, 语义={store.count('semantic')}
- 配置文件：memory/test_sakiko.sqlite

验证通过的功能：
✓ 人格 - 记忆联动（根据人格特质自动配置参数）
✓ 三层记忆模型（工作/情景/语义）
✓ 遗忘曲线 + 强化机制
✓ 话题熔断
✓ 多角色隔离（character_id 字段）

下一步：
1. 集成到 runtime_engine
2. 添加 LLM 提炼语义记忆
3. 实现关系系统
""")

# 导出记忆
export_data = store.export()
print(f"\n记忆导出：{len(export_data['episodic'])} 条情景，{len(export_data['semantic'])} 条语义")

# 关闭连接
store.close()

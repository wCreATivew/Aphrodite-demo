# -*- coding: utf-8 -*-
"""
记忆系统模块

提供：
- 记忆存储（SQLite + FAISS）
- 三层记忆模型（工作/情景/语义）
- 人格感知配置
- 遗忘曲线 + 强化机制
- 话题熔断
"""

from .schemas import (
    MemoryConfig,
    MemoryTag,
    EpisodicMemory,
    SemanticMemory,
    WorkingMemory,
    TopicBreakerState,
    memory_weight,
    recency_score,
)

from .store import MemoryStore

__all__ = [
    # 数据结构
    "MemoryConfig",
    "MemoryTag",
    "EpisodicMemory",
    "SemanticMemory",
    "WorkingMemory",
    "TopicBreakerState",
    
    # 工具函数
    "memory_weight",
    "recency_score",
    
    # 核心类
    "MemoryStore",
]

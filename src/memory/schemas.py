# -*- coding: utf-8 -*-
"""
记忆系统数据结构定义

三层记忆模型：
- 工作记忆 (Working): 短期上下文，session 内有效
- 情景记忆 (Episodic): 具体事件，带时间戳、情绪标记
- 语义记忆 (Semantic): 提炼的知识，从情景记忆中归纳
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Literal, Tuple
import time
import math


@dataclass
class MemoryConfig:
    """
    记忆系统配置
    
    支持人格感知配置（PersonaMemoryConfig）
    """
    # 检索权重
    semantic_weight: float = 0.75   # 语义相似度
    recency_weight: float = 0.15    # 时间新鲜度
    emotion_weight: float = 0.05    # 情绪相关性
    task_weight: float = 0.05       # 任务相关性
    
    # 遗忘参数
    half_life_days: float = 14.0    # 半衰期
    alpha_reinforce: float = 0.08   # 见过次数的加固系数
    
    # 主动搭话
    idle_threshold_sec: int = 20    # 多久没输入触发搭话
    max_nudges: int = 3             # 最多主动几次
    
    # 情绪影响
    emotion_bias_retrieval: bool = True  # 情绪好时更容易想起开心的事
    
    # 话题熔断
    breaker_window_sec: int = 180        # 短时间窗口
    breaker_drop_ratio: float = 0.30     # 权重降到 30% 以下触发熔断
    breaker_min_dom_weight: float = 0.45 # 主导标签最低权重
    
    @classmethod
    def from_persona_config(cls, persona_config) -> "MemoryConfig":
        """从人格配置转换"""
        if persona_config is None:
            return cls()
        
        return cls(
            semantic_weight=persona_config.semantic_weight,
            recency_weight=persona_config.recency_weight,
            emotion_weight=persona_config.emotion_weight,
            task_weight=persona_config.task_weight,
            half_life_days=persona_config.half_life_days,
            alpha_reinforce=persona_config.alpha_reinforce,
            idle_threshold_sec=persona_config.idle_threshold_sec,
            max_nudges=persona_config.max_nudges,
            emotion_bias_retrieval=persona_config.emotion_bias_retrieval,
        )


@dataclass
class MemoryTag:
    """记忆标签（带权重）"""
    phrase: str       # 标签短语
    weight: float     # 权重 0-1
    
    def to_dict(self) -> dict:
        return {"phrase": self.phrase, "weight": self.weight}
    
    @classmethod
    def from_dict(cls, data: dict) -> "MemoryTag":
        return cls(phrase=data["phrase"], weight=data["weight"])


@dataclass
class EpisodicMemory:
    """
    情景记忆
    
    记录具体事件：「2026-03-09 和用户第一次见面」
    """
    id: Optional[int] = None
    character_id: str = ""  # 角色 ID（多角色隔离）
    
    # 记忆内容
    text: str = ""
    tags: List[MemoryTag] = field(default_factory=list)
    
    # 时间信息
    created_at: int = field(default_factory=lambda: int(time.time()))
    last_seen: int = field(default_factory=lambda: int(time.time()))
    
    # 遗忘相关
    seen_count: int = 1       # 被检索次数
    strength: float = 0.7     # 基础强度 0-1
    archived: int = 0         # 是否归档（0=正常，1=归档）
    
    # 情景记忆特有
    event_timestamp: Optional[int] = None  # 事件发生时间
    emotion: Optional[str] = None          # 情绪标记（calm/happy/sad/angry...）
    importance: float = 0.5                # 重要性评分 0-1
    
    # 元数据
    source: Literal["user", "assistant", "system", "inference"] = "user"
    confidence: float = 1.0  # 置信度（推断的记忆置信度较低）
    
    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "character_id": self.character_id,
            "text": self.text,
            "tags": [t.to_dict() for t in self.tags],
            "created_at": self.created_at,
            "last_seen": self.last_seen,
            "seen_count": self.seen_count,
            "strength": self.strength,
            "archived": self.archived,
            "event_timestamp": self.event_timestamp,
            "emotion": self.emotion,
            "importance": self.importance,
            "source": self.source,
            "confidence": self.confidence,
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> "EpisodicMemory":
        return cls(
            id=data.get("id"),
            character_id=data.get("character_id", ""),
            text=data.get("text", ""),
            tags=[MemoryTag.from_dict(t) for t in data.get("tags", [])],
            created_at=data.get("created_at", int(time.time())),
            last_seen=data.get("last_seen", int(time.time())),
            seen_count=data.get("seen_count", 1),
            strength=data.get("strength", 0.7),
            archived=data.get("archived", 0),
            event_timestamp=data.get("event_timestamp"),
            emotion=data.get("emotion"),
            importance=data.get("importance", 0.5),
            source=data.get("source", "user"),
            confidence=data.get("confidence", 1.0),
        )


@dataclass
class SemanticMemory:
    """
    语义记忆
    
    提炼的知识：「用户喜欢咖啡」「用户在上海」
    从情景记忆中归纳，更稳定
    """
    id: Optional[int] = None
    character_id: str = ""
    
    # 记忆内容
    text: str = ""
    tags: List[MemoryTag] = field(default_factory=list)
    
    # 时间信息
    created_at: int = field(default_factory=lambda: int(time.time()))
    last_seen: int = field(default_factory=lambda: int(time.time()))
    
    # 遗忘相关
    seen_count: int = 1
    strength: float = 0.8  # 语义记忆更稳定
    archived: int = 0
    
    # 语义记忆特有
    source_memory_ids: List[int] = field(default_factory=list)  # 从哪些情景记忆提炼
    confidence: float = 0.9  # 提炼置信度
    category: str = "preference"  # preference/fact/belief/skill...
    
    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "character_id": self.character_id,
            "text": self.text,
            "tags": [t.to_dict() for t in self.tags],
            "created_at": self.created_at,
            "last_seen": self.last_seen,
            "seen_count": self.seen_count,
            "strength": self.strength,
            "archived": self.archived,
            "source_memory_ids": self.source_memory_ids,
            "confidence": self.confidence,
            "category": self.category,
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> "SemanticMemory":
        return cls(
            id=data.get("id"),
            character_id=data.get("character_id", ""),
            text=data.get("text", ""),
            tags=[MemoryTag.from_dict(t) for t in data.get("tags", [])],
            created_at=data.get("created_at", int(time.time())),
            last_seen=data.get("last_seen", int(time.time())),
            seen_count=data.get("seen_count", 1),
            strength=data.get("strength", 0.8),
            archived=data.get("archived", 0),
            source_memory_ids=data.get("source_memory_ids", []),
            confidence=data.get("confidence", 0.9),
            category=data.get("category", "preference"),
        )


@dataclass
class WorkingMemory:
    """
    工作记忆
    
    当前对话的短期上下文，session 内有效
    容量有限，会自然遗忘
    """
    character_id: str = ""
    messages: List[Dict[str, str]] = field(default_factory=list)
    max_turns: int = 6  # 最多保留 6 轮对话
    
    def add_message(self, role: str, content: str):
        """添加消息"""
        self.messages.append({"role": role, "content": content})
        
        # 超出容量则移除最早的
        while len(self.messages) > self.max_turns * 2:
            self.messages.pop(0)
    
    def get_messages(self) -> List[Dict[str, str]]:
        """获取所有消息"""
        return self.messages
    
    def clear(self):
        """清空工作记忆"""
        self.messages = []
    
    def to_dict(self) -> dict:
        return {
            "character_id": self.character_id,
            "messages": self.messages,
            "max_turns": self.max_turns,
        }


# ========== 遗忘曲线计算 ==========

HALF_LIFE_DAYS = 14.0
LAMBDA = math.log(2) / (HALF_LIFE_DAYS * 86400)  # 秒
ALPHA = 0.08  # 加固系数


def memory_weight(
    now_ts: int,
    last_seen: int,
    seen_count: int,
    strength: float,
    half_life_days: float = HALF_LIFE_DAYS,
    alpha: float = ALPHA,
) -> float:
    """
    计算记忆权重（考虑遗忘 + 强化）
    
    Args:
        now_ts: 当前时间戳
        last_seen: 上次检索时间
        seen_count: 见过次数
        strength: 基础强度
        half_life_days: 半衰期
        alpha: 加固系数
    
    Returns:
        记忆权重 0-1
    """
    dt = max(0, now_ts - int(last_seen))
    
    # 指数衰减
    lambda_val = math.log(2) / (half_life_days * 86400)
    decay = math.exp(-lambda_val * dt)
    
    # 见过次数的加固
    reinforce = alpha * math.log(1 + max(0, int(seen_count)))
    
    # 综合权重
    w = strength * decay + reinforce
    
    # clip 到 [0, 1]
    return max(0.0, min(1.0, w))


def recency_score(
    last_seen: int,
    now_ts: Optional[int] = None,
    half_life_days: float = 7.0,
) -> float:
    """
    计算时间新鲜度分数
    
    Args:
        last_seen: 上次检索时间
        now_ts: 当前时间戳
        half_life_days: 半衰期（默认 7 天）
    
    Returns:
        新鲜度分数 0-1（越新越接近 1）
    """
    if now_ts is None:
        now_ts = int(time.time())
    
    if last_seen <= 0:
        return 0.0
    
    age = max(0, now_ts - last_seen)
    tau = (half_life_days * 86400.0) / math.log(2.0)
    
    return float(math.exp(-age / tau))


# ========== 话题熔断 ==========

@dataclass
class TopicBreakerState:
    """话题熔断状态"""
    active: bool = False
    tag: str = ""
    since_ts: float = 0.0
    last_dom_tag: str = ""
    last_dom_weight: float = 0.0
    last_dom_ts: float = 0.0
    
    def to_dict(self) -> dict:
        return {
            "active": self.active,
            "tag": self.tag,
            "since_ts": self.since_ts,
            "last_dom_tag": self.last_dom_tag,
            "last_dom_weight": self.last_dom_weight,
            "last_dom_ts": self.last_dom_ts,
        }

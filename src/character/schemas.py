# -*- coding: utf-8 -*-
"""
角色系统数据结构定义

核心设计：
- CharacterProfile: 完整角色设定（人格、声音、语法、环境、立场）
- PersonaMemoryConfig: 人格对应的记忆系统参数
- CharacterState: 角色运行时状态
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Literal
import json


@dataclass
class VoiceProfile:
    """声音配置（支持 TTS/声音克隆）"""
    voice_id: str = ""  # ElevenLabs/Azure 声音 ID
    voice_name: str = ""  # 人类可读名称
    clone_reference: Optional[str] = None  # 声音克隆参考音频路径
    style: str = "neutral"  # neutral/excited/calm/sad
    pitch: float = 0.0  # -2.0 ~ +2.0 semitones
    rate: float = 1.0  # 0.5 ~ 2.0
    volume: float = 1.0  # 0.0 ~ 1.0
    
    def to_dict(self) -> dict:
        return {
            "voice_id": self.voice_id,
            "voice_name": self.voice_name,
            "clone_reference": self.clone_reference,
            "style": self.style,
            "pitch": self.pitch,
            "rate": self.rate,
            "volume": self.volume,
        }


@dataclass
class SpeechPattern:
    """语法/表达风格配置"""
    vocabulary_level: Literal["simple", "normal", "advanced", "academic"] = "normal"
    sentence_structure: Literal["short", "medium", "long", "mixed"] = "medium"
    formality: float = 0.5  # 0=随意，1=正式
    emoji_usage: float = 0.0  # 0=不用，1=频繁
    catchphrases: List[str] = field(default_factory=list)  # 口头禅
    forbidden_words: List[str] = field(default_factory=list)  # 禁用词
    language: str = "zh-CN"  # 语言代码
    
    def to_dict(self) -> dict:
        return {
            "vocabulary_level": self.vocabulary_level,
            "sentence_structure": self.sentence_structure,
            "formality": self.formality,
            "emoji_usage": self.emoji_usage,
            "catchphrases": self.catchphrases,
            "forbidden_words": self.forbidden_words,
            "language": self.language,
        }


@dataclass
class WorldContext:
    """角色所处的世界/环境设定"""
    world_name: str = ""  # 世界名称（如"霍格沃茨"）
    time_period: str = ""  # 时代（如"1990 年代"）
    location: str = ""  # 当前位置
    social_context: str = ""  # 社会背景
    current_events: List[str] = field(default_factory=list)  # 正在发生的事件
    rules: List[str] = field(default_factory=list)  # 世界规则/物理法则
    
    def to_dict(self) -> dict:
        return {
            "world_name": self.world_name,
            "time_period": self.time_period,
            "location": self.location,
            "social_context": self.social_context,
            "current_events": self.current_events,
            "rules": self.rules,
        }


@dataclass
class CharacterStance:
    """角色立场/价值观"""
    moral_alignment: Literal["lawful_good", "neutral_good", "chaotic_good", 
                             "lawful_neutral", "true_neutral", "chaotic_neutral",
                             "lawful_evil", "neutral_evil", "chaotic_evil"] = "true_neutral"
    core_values: List[str] = field(default_factory=list)  # 核心价值观（优先级排序）
    beliefs: List[str] = field(default_factory=list)  # 信念
    loyalties: List[str] = field(default_factory=list)  # 忠诚对象
    enemies: List[str] = field(default_factory=list)  # 敌对对象
    boundaries: List[str] = field(default_factory=list)  # 绝对不做的事
    
    def to_dict(self) -> dict:
        return {
            "moral_alignment": self.moral_alignment,
            "core_values": self.core_values,
            "beliefs": self.beliefs,
            "loyalties": self.loyalties,
            "enemies": self.enemies,
            "boundaries": self.boundaries,
        }


@dataclass
class PersonaTraits:
    """人格特质（大五人格简化版）"""
    openness: float = 0.5      # 开放性 0-1
    conscientiousness: float = 0.5  # 尽责性
    extraversion: float = 0.5   # 外向性
    agreeableness: float = 0.5  # 宜人性
    neuroticism: float = 0.5    # 神经质
    
    # 简化标签
    tags: List[str] = field(default_factory=list)  # 如"傲娇"、"温柔"、"毒舌"
    
    def to_dict(self) -> dict:
        return {
            "openness": self.openness,
            "conscientiousness": self.conscientiousness,
            "extraversion": self.extraversion,
            "agreeableness": self.agreeableness,
            "neuroticism": self.neuroticism,
            "tags": self.tags,
        }


@dataclass
class CharacterProfile:
    """
    完整角色设定
    
    生成流程：
    1. 用户输入简短描述（"我想要赫敏"）
    2. 联网搜索角色信息
    3. LLM 补全人格、声音、语法、环境、立场
    4. 生成 CharacterProfile
    5. 根据人格配置记忆系统参数
    """
    # 基础身份
    id: str = ""  # 角色唯一 ID
    name: str = ""
    source: str = ""  # 来源作品（如"哈利·波特"）
    description: str = ""  # 角色描述
    
    # 核心组件
    persona: PersonaTraits = field(default_factory=PersonaTraits)
    voice: VoiceProfile = field(default_factory=VoiceProfile)
    speech: SpeechPattern = field(default_factory=SpeechPattern)
    context: WorldContext = field(default_factory=WorldContext)
    stance: CharacterStance = field(default_factory=CharacterStance)
    
    # 记忆系统配置（根据人格自动生成）
    memory_config: Optional[PersonaMemoryConfig] = None
    
    # 元数据
    created_at: float = field(default_factory=lambda: __import__('time').time())
    version: str = "1.0"
    
    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "source": self.source,
            "description": self.description,
            "persona": self.persona.to_dict(),
            "voice": self.voice.to_dict(),
            "speech": self.speech.to_dict(),
            "context": self.context.to_dict(),
            "stance": self.stance.to_dict(),
            "memory_config": self.memory_config.to_dict() if self.memory_config else None,
            "created_at": self.created_at,
            "version": self.version,
        }
    
    def to_json(self, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=indent)
    
    @classmethod
    def from_dict(cls, data: dict) -> "CharacterProfile":
        """从字典加载角色"""
        profile = cls()
        profile.id = data.get("id", "")
        profile.name = data.get("name", "")
        profile.source = data.get("source", "")
        profile.description = data.get("description", "")
        
        if "persona" in data:
            profile.persona = PersonaTraits(**data["persona"])
        if "voice" in data:
            profile.voice = VoiceProfile(**data["voice"])
        if "speech" in data:
            profile.speech = SpeechPattern(**data["speech"])
        if "context" in data:
            profile.context = WorldContext(**data["context"])
        if "stance" in data:
            profile.stance = CharacterStance(**data["stance"])
        if "memory_config" in data and data["memory_config"]:
            profile.memory_config = PersonaMemoryConfig(**data["memory_config"])
        
        profile.created_at = data.get("created_at", __import__('time').time())
        profile.version = data.get("version", "1.0")
        
        return profile


@dataclass
class PersonaMemoryConfig:
    """
    人格对应的记忆系统配置
    
    不同人格需要不同的记忆策略：
    - 温柔陪伴型：高情绪权重、慢遗忘、高主动搭话
    - 执行教练型：高任务权重、快遗忘、中主动搭话
    - 分析师型：高事实权重、中遗忘、低主动搭话
    """
    persona_id: str = ""
    
    # 检索权重（总和不必为 1，会归一化）
    semantic_weight: float = 0.75   # 语义相似度
    recency_weight: float = 0.15    # 时间新鲜度
    emotion_weight: float = 0.05    # 情绪相关性（陪伴型更高）
    task_weight: float = 0.05       # 任务相关性（教练型更高）
    
    # 遗忘参数
    half_life_days: float = 14.0    # 半衰期（陪伴型=21，教练型=7）
    alpha_reinforce: float = 0.08   # 见过次数的加固系数
    
    # 主动搭话
    idle_threshold_sec: int = 20    # 多久没输入触发搭话
    max_nudges: int = 3             # 最多主动几次
    
    # 情绪影响
    emotion_bias_retrieval: bool = True  # 情绪好时更容易想起开心的事
    
    @classmethod
    def for_persona_type(cls, persona_type: str) -> "PersonaMemoryConfig":
        """根据人格类型生成默认配置"""
        configs = {
            # 温柔陪伴型（如 Aphrodite）
            "companion": cls(
                persona_id="companion",
                semantic_weight=0.65,
                emotion_weight=0.15,
                recency_weight=0.15,
                task_weight=0.05,
                half_life_days=21.0,
                idle_threshold_sec=15,
                max_nudges=4,
                emotion_bias_retrieval=True,
            ),
            
            # 执行教练型
            "coach": cls(
                persona_id="coach",
                semantic_weight=0.60,
                task_weight=0.20,
                recency_weight=0.15,
                emotion_weight=0.05,
                half_life_days=7.0,
                idle_threshold_sec=30,
                max_nudges=2,
                emotion_bias_retrieval=False,
            ),
            
            # 分析师型
            "analyst": cls(
                persona_id="analyst",
                semantic_weight=0.80,
                recency_weight=0.10,
                emotion_weight=0.02,
                task_weight=0.08,
                half_life_days=14.0,
                idle_threshold_sec=60,
                max_nudges=1,
                emotion_bias_retrieval=False,
            ),
            
            # 代码代理型
            "codex": cls(
                persona_id="codex",
                semantic_weight=0.85,
                task_weight=0.10,
                recency_weight=0.05,
                emotion_weight=0.0,
                half_life_days=5.0,
                idle_threshold_sec=120,
                max_nudges=0,  # 不主动搭话
                emotion_bias_retrieval=False,
            ),
        }
        
        return configs.get(persona_type.lower(), configs["companion"])
    
    def to_dict(self) -> dict:
        return {
            "persona_id": self.persona_id,
            "semantic_weight": self.semantic_weight,
            "recency_weight": self.recency_weight,
            "emotion_weight": self.emotion_weight,
            "task_weight": self.task_weight,
            "half_life_days": self.half_life_days,
            "alpha_reinforce": self.alpha_reinforce,
            "idle_threshold_sec": self.idle_threshold_sec,
            "max_nudges": self.max_nudges,
            "emotion_bias_retrieval": self.emotion_bias_retrieval,
        }


@dataclass
class CharacterState:
    """角色运行时状态"""
    character_id: str = ""
    
    # 情绪状态
    emotion: str = "calm"
    energy: int = 60      # 0-100
    affinity: int = 20    # 亲密度 0-100
    
    # 对话状态
    topic: str = "smalltalk"
    topic_prev: Optional[str] = None
    
    # 空闲状态
    idle_pressure: int = 0      # 沉默压力 0-100
    idle_stage: int = 0         # 触发阶段
    last_user_ts: float = 0.0   # 上次用户输入时间
    
    # 关系状态（简化版）
    trust: float = 0.5
    intimacy: float = 0.3
    respect: float = 0.7
    tension: float = 0.1
    
    def to_dict(self) -> dict:
        return {
            "character_id": self.character_id,
            "emotion": self.emotion,
            "energy": self.energy,
            "affinity": self.affinity,
            "topic": self.topic,
            "topic_prev": self.topic_prev,
            "idle_pressure": self.idle_pressure,
            "idle_stage": self.idle_stage,
            "last_user_ts": self.last_user_ts,
            "trust": self.trust,
            "intimacy": self.intimacy,
            "respect": self.respect,
            "tension": self.tension,
        }

# -*- coding: utf-8 -*-
"""
角色系统模块

提供：
- 角色生成（从用户简短描述生成完整人格设定）
- 人格 - 记忆联动（根据人格自动配置记忆参数）
- 角色状态管理
"""

from .schemas import (
    CharacterProfile,
    PersonaTraits,
    VoiceProfile,
    SpeechPattern,
    WorldContext,
    CharacterStance,
    PersonaMemoryConfig,
    CharacterState,
)

from .generator import (
    CharacterGenerator,
    generate_character_from_query,
)

__all__ = [
    # 数据结构
    "CharacterProfile",
    "PersonaTraits",
    "VoiceProfile",
    "SpeechPattern",
    "WorldContext",
    "CharacterStance",
    "PersonaMemoryConfig",
    "CharacterState",
    
    # 生成器
    "CharacterGenerator",
    "generate_character_from_query",
]

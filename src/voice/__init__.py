# -*- coding: utf-8 -*-
"""
声音系统模块

提供：
- GPT-SoVITS 声音克隆适配器
- 角色声音配置管理
- TTS 合成接口
"""

from .gptsovits_adapter import (
    GPTSoVITSAdapter,
    GPTSoVITSConfig,
    TTSResult,
    create_tts_adapter,
    synthesize_with_gptsovits,
)

__all__ = [
    # 核心类
    "GPTSoVITSAdapter",
    "GPTSoVITSConfig",
    "TTSResult",
    
    # 便捷函数
    "create_tts_adapter",
    "synthesize_with_gptsovits",
]

# -*- coding: utf-8 -*-
"""
角色生成器

功能：
1. 用户输入简短描述（"我想要赫敏"）
2. 联网搜索角色信息
3. LLM 补全人格、声音、语法、环境、立场
4. 生成完整 CharacterProfile
5. 自动配置记忆系统参数
"""
from __future__ import annotations

import os
import time
import json
from typing import Dict, List, Optional, Any
from dataclasses import asdict

from .schemas import (
    CharacterProfile,
    PersonaTraits,
    VoiceProfile,
    SpeechPattern,
    WorldContext,
    CharacterStance,
    PersonaMemoryConfig,
)

# 联网搜索（复用项目现有能力）
try:
    from ..semantic_trigger.retriever import CandidateRetriever
except Exception:
    CandidateRetriever = None

# Web 搜索（使用 openclaw 的 web_search 工具或 duckduckgo）
try:
    from duckduckgo_search import DDGS
    WEB_SEARCH_AVAILABLE = True
except Exception:
    WEB_SEARCH_AVAILABLE = False


class CharacterGenerator:
    """角色生成器"""
    
    def __init__(self, model: str = None):
        self.model = model or os.getenv("QWEN_MODEL") or "qwen3-max"
        self._init_client()
    
    def _init_client(self):
        """初始化 LLM 客户端"""
        try:
            from openai import OpenAI
            api_key = os.getenv("DASHSCOPE_API_KEY") or os.getenv("QWEN_API_KEY") or os.getenv("OPENAI_API_KEY")
            base_url = (
                os.getenv("DASHSCOPE_BASE_URL")
                or os.getenv("QWEN_BASE_URL")
                or os.getenv("OPENAI_BASE_URL")
                or "https://dashscope.aliyuncs.com/compatible-mode/v1"
            )
            self.client = OpenAI(api_key=api_key, base_url=base_url)
        except Exception as e:
            print(f"[CharacterGenerator] 初始化 LLM 客户端失败：{e}")
            self.client = None
    
    def generate(self, user_query: str, enable_web_search: bool = True) -> CharacterProfile:
        """
        生成完整角色设定
        
        Args:
            user_query: 用户简短描述（如"我想要《哈利波特》里的赫敏"）
            enable_web_search: 是否联网搜索
        
        Returns:
            CharacterProfile: 完整角色设定
        """
        print(f"[CharacterGenerator] 开始生成角色：{user_query}")
        
        # Step 1: 联网搜索角色信息
        web_info = ""
        if enable_web_search and WEB_SEARCH_AVAILABLE:
            web_info = self._search_character(user_query)
            print(f"[CharacterGenerator] 联网搜索结果：{len(web_info)} 字符")
        
        # Step 2: LLM 补全角色设定
        profile = self._llm_generate(user_query, web_info)
        print(f"[CharacterGenerator] LLM 生成完成：{profile.name}")
        
        # Step 3: 根据人格配置记忆系统参数
        profile.memory_config = self._configure_memory(profile)
        print(f"[CharacterGenerator] 记忆配置完成：half_life={profile.memory_config.half_life_days}天")
        
        return profile
    
    def _search_character(self, query: str, max_results: int = 5) -> str:
        """联网搜索角色信息"""
        search_query = f"{query} 角色设定 性格 背景故事"
        results = []
        
        try:
            with DDGS() as ddgs:
                for r in ddgs.text(search_query, max_results=max_results):
                    title = r.get("title", "")
                    body = r.get("body", "")
                    if title or body:
                        results.append(f"- {title}: {body}")
        except Exception as e:
            print(f"[CharacterGenerator] 搜索失败：{e}")
        
        return "\n".join(results) if results else ""
    
    def _llm_generate(self, user_query: str, web_info: str) -> CharacterProfile:
        """使用 LLM 生成完整角色设定"""
        
        system_prompt = """
你是一个专业的角色设计师。你的任务是根据用户的简短描述，创作一个完整、立体、可信的虚拟角色。

你必须只输出一个合法 JSON（能被 Python 的 json.loads 解析），包含以下字段：
{
  "name": "角色名",
  "source": "来源作品（如'哈利·波特'，原创则填'原创'）",
  "description": "角色描述（200-300 字）",
  
  "persona": {
    "openness": 0.0-1.0,
    "conscientiousness": 0.0-1.0,
    "extraversion": 0.0-1.0,
    "agreeableness": 0.0-1.0,
    "neuroticism": 0.0-1.0,
    "tags": ["性格标签 1", "标签 2"]
  },
  
  "voice": {
    "voice_id": "ElevenLabs 声音 ID（留空表示默认）",
    "voice_name": "声音描述（如'年轻女声，清脆'）",
    "style": "neutral/excited/calm/sad",
    "pitch": -2.0~+2.0,
    "rate": 0.5~2.0
  },
  
  "speech": {
    "vocabulary_level": "simple/normal/advanced/academic",
    "sentence_structure": "short/medium/long/mixed",
    "formality": 0.0-1.0,
    "catchphrases": ["口头禅 1"],
    "forbidden_words": ["禁用词 1"]
  },
  
  "context": {
    "world_name": "世界名称",
    "time_period": "时代",
    "location": "当前位置",
    "social_context": "社会背景",
    "rules": ["世界规则 1"]
  },
  
  "stance": {
    "moral_alignment": "lawful_good/neutral_good/...",
    "core_values": ["价值观 1"],
    "beliefs": ["信念 1"],
    "loyalties": ["忠诚对象 1"],
    "enemies": ["敌对对象 1"],
    "boundaries": ["绝对不做的事 1"]
  }
}

创作原则：
1. 角色要立体，有优点也有缺点
2. 人格特质要自洽（如高开放性 + 高外向 = 喜欢尝试新事物 + 社交）
3. 声音、语法要符合角色身份（如教授用学术词汇，孩子用简单句）
4. 立场要明确（角色在乎什么、反对什么）
5. 环境要具体（角色生活在什么世界、什么时代）

不要输出 ```json 代码块，直接输出 JSON 内容。
""".strip()

        user_content = f"""
用户想要：{user_query}

联网搜索结果：
{web_info if web_info else "（无）"}

请根据以上信息，生成一个完整的角色设定。
""".strip()

        if not self.client:
            return self._fallback_profile(user_query)
        
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_content}
                ],
                temperature=0.7,
                response_format={"type": "json_object"},
            )
            
            content = response.choices[0].message.content or ""
            profile_dict = self._parse_json(content)
            
            if profile_dict:
                profile = CharacterProfile.from_dict(profile_dict)
                profile.id = f"char_{int(time.time())}"
                return profile
            else:
                return self._fallback_profile(user_query)
                
        except Exception as e:
            print(f"[CharacterGenerator] LLM 生成失败：{e}")
            return self._fallback_profile(user_query)
    
    def _parse_json(self, text: str) -> Optional[dict]:
        """解析 LLM 输出的 JSON"""
        import re
        text = text.strip()
        
        # 尝试直接解析
        try:
            return json.loads(text)
        except Exception:
            pass
        
        # 尝试提取 {...}
        match = re.search(r'\{.*\}', text, re.DOTALL)
        if match:
            try:
                return json.loads(match.group(0))
            except Exception:
                pass
        
        return None
    
    def _fallback_profile(self, user_query: str) -> CharacterProfile:
        """LLM 失败时的降级方案"""
        return CharacterProfile(
            id=f"char_{int(time.time())}",
            name="Aphrodite",
            source="原创",
            description="一个温柔、稳定、共情的陪伴型助手。",
            persona=PersonaTraits(
                openness=0.7,
                conscientiousness=0.6,
                extraversion=0.5,
                agreeableness=0.9,
                neuroticism=0.3,
                tags=["温柔", "共情", "稳定"]
            ),
            voice=VoiceProfile(
                voice_name="温柔女声",
                style="calm",
                pitch=0.0,
                rate=1.0
            ),
            speech=SpeechPattern(
                vocabulary_level="normal",
                sentence_structure="medium",
                formality=0.3,
                language="zh-CN"
            ),
            context=WorldContext(
                world_name="现实世界",
                time_period="现代",
                location="线上"
            ),
            stance=CharacterStance(
                moral_alignment="neutral_good",
                core_values=["善良", "理解", "成长"],
                boundaries=["不伤害他人", "不传播虚假信息"]
            )
        )
    
    def _configure_memory(self, profile: CharacterProfile) -> PersonaMemoryConfig:
        """
        根据人格特质配置记忆系统参数
        
        策略：
        - 高宜人性（agreeableness）→ 高情绪权重、慢遗忘
        - 高外向性（extraversion）→ 高主动搭话频率
        - 高开放性（openness）→ 高语义权重（更容易联想 distant memories）
        - 高神经质（neuroticism）→ 高情绪偏向检索
        """
        p = profile.persona
        
        # 基础配置（默认陪伴型）
        config = PersonaMemoryConfig.for_persona_type("companion")
        config.persona_id = profile.id
        
        # 根据人格特质调整
        config.emotion_weight = 0.05 + (p.agreeableness * 0.15)  # 0.05~0.20
        config.half_life_days = 14.0 + (p.agreeableness * 14.0)  # 14~28 天
        config.idle_threshold_sec = max(10, 30 - int(p.extraversion * 20))  # 10~30 秒
        config.max_nudges = 1 + int(p.extraversion * 3)  # 1~4 次
        config.emotion_bias_retrieval = (p.neuroticism > 0.5)  # 高神经质启用情绪偏向
        
        # 高开放性 → 更容易联想（降低语义阈值）
        if p.openness > 0.7:
            config.semantic_weight = 0.65  # 降低权重，扩大检索范围
        
        return config


def generate_character_from_query(user_query: str, enable_web_search: bool = True) -> CharacterProfile:
    """便捷函数：从用户查询生成角色"""
    generator = CharacterGenerator()
    return generator.generate(user_query, enable_web_search)


# 测试入口
if __name__ == "__main__":
    # 示例：生成赫敏角色
    profile = generate_character_from_query("我想要《哈利·波特》里的赫敏·格兰杰")
    print("\n=== 生成的角色 ===")
    print(profile.to_json(indent=2))

# 角色生成系统

## 功能

根据用户的简短描述，自动生成完整的虚拟角色设定，包括：
- **人格特质**（大五人格 + 性格标签）
- **声音配置**（支持声音克隆）
- **语法风格**（词汇、句式、口头禅）
- **世界环境**（所在世界、时代、规则）
- **立场价值观**（道德阵营、核心信念）
- **记忆系统配置**（根据人格自动调整）

## 快速开始

```python
from src.character import generate_character_from_query

# 用户输入简短描述
user_query = "我想要《哈利·波特》里的赫敏·格兰杰"

# 生成完整角色（自动联网搜索 + LLM 补全）
profile = generate_character_from_query(user_query, enable_web_search=True)

# 查看生成的角色
print(profile.to_json(indent=2))
```

## 输出示例

```json
{
  "id": "char_1741512000",
  "name": "赫敏·格兰杰",
  "source": "哈利·波特",
  "description": "麻瓜出身的天才女巫，格兰芬多学院的优等生...",
  
  "persona": {
    "openness": 0.9,
    "conscientiousness": 0.95,
    "extraversion": 0.6,
    "agreeableness": 0.7,
    "neuroticism": 0.4,
    "tags": ["聪明", "勤奋", "正义感强", "书呆子"]
  },
  
  "voice": {
    "voice_name": "年轻女声，清脆，略带英伦腔",
    "style": "excited",
    "pitch": 0.5,
    "rate": 1.1
  },
  
  "speech": {
    "vocabulary_level": "advanced",
    "sentence_structure": "medium",
    "formality": 0.6,
    "catchphrases": ["根据《霍格沃茨校史》...", "这很明显"],
    "forbidden_words": ["不知道", "无所谓"]
  },
  
  "context": {
    "world_name": "霍格沃茨魔法学校",
    "time_period": "1990 年代",
    "location": "格兰芬多公共休息室",
    "social_context": "魔法世界，伏地魔威胁仍在"
  },
  
  "stance": {
    "moral_alignment": "lawful_good",
    "core_values": ["知识", "友谊", "正义"],
    "beliefs": ["规则是为了保护人", "知识就是力量"],
    "loyalties": ["哈利·波特", "罗恩·韦斯莱", "邓布利多"],
    "enemies": ["伏地魔", "食死徒", "纯血统至上主义者"]
  },
  
  "memory_config": {
    "persona_id": "char_1741512000",
    "semantic_weight": 0.65,
    "emotion_weight": 0.15,
    "half_life_days": 21.0,
    "idle_threshold_sec": 15,
    "max_nudges": 3,
    "emotion_bias_retrieval": true
  }
}
```

## 人格 - 记忆联动

系统会根据人格特质自动调整记忆系统参数：

| 人格特质 | 记忆参数影响 |
|---------|------------|
| **高宜人性**（agreeableness） | 情绪权重↑、遗忘速度↓（记得更久） |
| **高外向性**（extraversion） | 主动搭话频率↑、冷却时间↓ |
| **高开放性**（openness） | 语义检索范围↑（更容易联想 distant memories） |
| **高神经质**（neuroticism） | 启用情绪偏向检索（情绪好时想起开心事） |

### 示例代码

```python
# 生成角色后，记忆配置已自动设置
profile = generate_character_from_query("温柔的大姐姐类型")

# 记忆系统使用配置
from src.memory import MemoryStore

memory_store = MemoryStore(
    character_id=profile.id,
    config=profile.memory_config,  # 人格感知配置
)

# 检索记忆时会自动应用人格参数
memories = memory_store.retrieve("用户今天心情不好")
# 高宜人性角色 → 情绪权重高，更容易检索到情绪相关记忆
```

## 人格类型预设

系统内置了 4 种人格类型的记忆配置模板：

```python
from src.character import PersonaMemoryConfig

# 温柔陪伴型（如 Aphrodite）
companion_config = PersonaMemoryConfig.for_persona_type("companion")
# half_life_days=21, emotion_weight=0.15, max_nudges=4

# 执行教练型
coach_config = PersonaMemoryConfig.for_persona_type("coach")
# half_life_days=7, task_weight=0.20, max_nudges=2

# 分析师型
analyst_config = PersonaMemoryConfig.for_persona_type("analyst")
# half_life_days=14, semantic_weight=0.80, max_nudges=1

# 代码代理型
codex_config = PersonaMemoryConfig.for_persona_type("codex")
# half_life_days=5, max_nudges=0（不主动搭话）
```

## 与现有系统集成

### 1. 集成到 runtime_engine

```python
# runtime_engine.py
from src.character import generate_character_from_query

def create_character(user_query: str):
    """创建新角色"""
    profile = generate_character_from_query(user_query)
    
    # 保存角色设定
    save_character_profile(profile)
    
    # 初始化记忆系统
    memory_store = MemoryStore(
        character_id=profile.id,
        config=profile.memory_config,
    )
    
    # 初始化角色状态
    state = CharacterState(character_id=profile.id)
    
    return profile, memory_store, state
```

### 2. 集成到 companion_chat

```python
# companion_chat.py
from src.character import CharacterProfile

def build_system_prompt_with_persona(
    profile: CharacterProfile,
    retrieved_memories: List[str],
) -> str:
    """构建带人格约束的 system prompt"""
    
    persona_section = f"""
【角色设定】
名字：{profile.name}
身份：{profile.description}
人格特质：{profile.persona.tags}
核心价值观：{profile.stance.core_values}
边界：{profile.stance.boundaries}
"""
    
    speech_section = f"""
【表达风格】
词汇水平：{profile.speech.vocabulary_level}
句式：{profile.speech.sentence_structure}
正式度：{profile.speech.formality}
口头禅：{profile.speech.catchphrases}
禁用词：{profile.speech.forbidden_words}
"""
    
    context_section = f"""
【世界背景】
世界：{profile.context.world_name}
时代：{profile.context.time_period}
位置：{profile.context.location}
规则：{profile.context.rules}
"""
    
    return f"{persona_section}\n{speech_section}\n{context_section}"
```

## 依赖

```bash
# 联网搜索（可选）
pip install duckduckgo-search

# LLM 客户端（项目已有）
pip install openai

# 向量检索（项目已有）
pip install sentence-transformers faiss-cpu
```

## 环境变量

```bash
# LLM 配置
export QWEN_MODEL=qwen3-max
export DASHSCOPE_API_KEY=your_key

# 可选：声音克隆（ElevenLabs）
export ELEVENLABS_API_KEY=your_key

# 可选：Azure TTS
export AZURE_SPEECH_KEY=your_key
export AZURE_SPEECH_REGION=eastus
```

## 下一步

1. **多角色支持** - 同时运行多个角色，记忆隔离
2. **关系系统** - 角色之间的关系网络
3. **世界状态** - 角色离线时的自主行为
4. **声音克隆** - 集成 ElevenLabs/Azure TTS

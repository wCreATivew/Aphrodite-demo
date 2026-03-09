# 声音系统 - GPT-SoVITS 集成

## 为什么选择 GPT-SoVITS

**对比其他 TTS 方案：**

| 方案 | 克隆质量 | 少样本支持 | 中文效果 | 情感控制 | 开源 | 实时性 |
|------|---------|-----------|---------|---------|------|--------|
| **GPT-SoVITS** | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ (1-5 分钟) | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ✅ | ✅ |
| ElevenLabs | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ❌ | ✅ |
| Azure TTS | ⭐⭐⭐⭐ | ⭐⭐ (需定制) | ⭐⭐⭐⭐ | ⭐⭐⭐ | ❌ | ✅ |
| VITS | ⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐ | ✅ | ⚠️ |
| Coqui TTS | ⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐ | ⭐⭐ | ✅ | ⚠️ |

**GPT-SoVITS 优势：**
- ✅ **少样本克隆**：1-5 分钟音频即可克隆声音
- ✅ **中文优化**：对中文支持极好，发音自然
- ✅ **情感控制**：支持 happy/sad/angry/fearful/disgusted/surprised/neutral
- ✅ **开源免费**：可商用，可本地部署
- ✅ **实时推理**：支持流式输出
- ✅ **多语言**：中文、英文、日文

---

## 快速开始

### 步骤 1：安装 GPT-SoVITS

```bash
# 克隆仓库
git clone https://github.com/RVC-Boss/GPT-SoVITS.git
cd GPT-SoVITS

# 安装依赖（需要 CUDA）
pip install -r requirements.txt

# 下载预训练模型
python download_models.py
```

**详细安装指南：** https://github.com/RVC-Boss/GPT-SoVITS/blob/main/docs/cn/README.md

### 步骤 2：启动推理服务

```bash
cd GPT-SoVITS
python api_v2.py --host 127.0.0.1 --port 9880
```

服务启动后会显示：
```
Running on http://127.0.0.1:9880
```

### 步骤 3：在本项目中使用

```python
from src.voice import create_tts_adapter

# 创建适配器
adapter = create_tts_adapter("http://127.0.0.1:9880")

# 合成语音
result = adapter.synthesize(
    text="你好，世界",
    ref_audio_path="reference.wav",  # 参考音频（角色声音样本）
    ref_text="你好，世界",  # 参考音频文本
    save_path="output.wav",
    emotion="neutral",
)

if result.success:
    print(f"合成成功：{result.audio_path}")
    print(f"时长：{result.duration_sec:.2f}秒")
    print(f"推理时间：{result.inference_time_ms:.1f}ms")
```

---

## 为角色克隆声音

### 方式 1：使用现成音频

```python
from src.voice import GPTSoVITSAdapter

adapter = GPTSoVITSAdapter()

# 为丰川祥子克隆声音
voice_config = adapter.clone_voice(
    character_name="丰川祥子",
    reference_audio="/path/to/sakiko_reference.wav",  # 1-5 分钟音频
    reference_text="音频对应的文字内容",
    output_dir="voices",
)

# 声音配置已保存到 voices/丰川祥子_voice.json
```

### 方式 2：从动漫/游戏提取音频

**工具推荐：**
- [youtube-dl](https://youtube-dl.org/) - 下载视频
- [Audacity](https://www.audacityteam.org/) - 剪辑音频
- [Ultimate Vocal Remover](https://github.com/Anjok07/ultimatevocalremovergui) - 人声分离

**流程：**
1. 下载包含角色语音的视频（如动画片段、游戏 PV）
2. 用 Audacity 剪辑出纯净人声（1-5 分钟）
3. 降噪处理（可选）
4. 导出为 WAV 格式（44.1kHz 或 48kHz）
5. 手动标注文字内容

### 方式 3：使用公开语音库

**推荐资源：**
- [VOICEROID 音声样本](https://www.ah-soft.com/voiceroid/)
- [CeVIO 免费素材](https://cevio.jp/)
- [Freesound.org](https://freesound.org/) - 搜索角色名

---

## 情感控制

GPT-SoVITS 支持 7 种情感：

```python
# 中性
adapter.synthesize("你好", emotion="neutral")

# 开心
adapter.synthesize("今天天气真好", emotion="happy")

# 悲伤
adapter.synthesize("为什么会这样...", emotion="sad")

# 愤怒
adapter.synthesize("我受够了", emotion="angry")

# 恐惧
adapter.synthesize("有...有什么东西", emotion="fearful")

# 厌恶
adapter.synthesize("太恶心了", emotion="disgusted")

# 惊讶
adapter.synthesize("什么？！", emotion="surprised")
```

### 与角色情绪联动

```python
from src.character import CharacterState

def get_emotion_for_state(state: CharacterState) -> str:
    """根据角色状态选择情感"""
    emotion_map = {
        "calm": "neutral",
        "warm": "happy",
        "gentle": "happy",
        "sad": "sad",
        "excited": "happy",
        "playful": "happy",
        "worried": "fearful",
        "tired": "sad",
        "angry": "angry",
    }
    return emotion_map.get(state.emotion, "neutral")

# 使用
state = CharacterState(emotion="sad")
result = adapter.synthesize(
    "我没事，真的...",
    emotion=get_emotion_for_state(state),
)
```

---

## 高级配置

### 参数调优

```python
from src.voice import GPTSoVITSConfig, GPTSoVITSAdapter

config = GPTSoVITSConfig(
    api_url="http://127.0.0.1:9880",
    text_lang="zh",  # zh/en/ja
    text_split_method="cut0",  # 文本切分方法
    batch_size=1,
    batch_threshold=0.75,
    speed_factor=1.0,  # 语速（0.5-2.0）
    streaming_mode=False,  # 流式输出
    emotion="neutral",
    
    # 高级参数
    top_k=5,
    top_p=1.0,
    temperature=1.0,
    repetition_penalty=1.35,
)

adapter = GPTSoVITSAdapter(config)
```

### 流式输出（实时播放）

```python
# 流式合成
for audio_chunk in adapter.synthesize_streaming(
    "这是一段很长的文字，需要边生成边播放",
    ref_audio_path="reference.wav",
    ref_text="参考文本",
):
    # 直接喂给音频播放器
    play_audio(audio_chunk)  # 需要实现播放函数
```

### 批量合成

```python
# 批量为多个角色合成
characters = [
    {"name": "丰川祥子", "ref_audio": "sakiko.wav", "ref_text": "样本"},
    {"name": "赫敏", "ref_audio": "hermione.wav", "ref_text": "sample"},
]

for char in characters:
    adapter.clone_voice(
        character_name=char["name"],
        reference_audio=char["ref_audio"],
        reference_text=char["ref_text"],
    )
```

---

## 与角色系统集成

### 1. 更新 CharacterProfile

```python
# src/character/schemas.py 已有 VoiceProfile
from src.voice import GPTSoVITSAdapter

# 为角色配置声音
profile.voice.voice_id = "丰川祥子"  # 角色名作为声音 ID
profile.voice.clone_reference = "voices/丰川祥子_reference.wav"
```

### 2. 集成到对话系统

```python
# runtime_engine.py
from src.voice import GPTSoVITSAdapter
from src.character import CharacterProfile

class RuntimeEngine:
    def __init__(self):
        self.tts_adapter = GPTSoVITSAdapter()
        self.current_profile: Optional[CharacterProfile] = None
    
    def set_character(self, profile: CharacterProfile):
        """切换角色"""
        self.current_profile = profile
        
        # 配置声音
        if profile.voice.clone_reference:
            self.tts_adapter.config.ref_audio_path = profile.voice.clone_reference
    
    def reply_with_voice(self, text: str, emotion: str = "neutral"):
        """带语音的回复"""
        if not self.current_profile:
            return
        
        # 根据角色状态调整情感
        if self.current_profile.persona.neuroticism > 0.6:
            # 高神经质角色：情绪波动大
            emotion = self._map_emotion(emotion)
        
        # 合成语音
        result = self.tts_adapter.synthesize(
            text=text,
            emotion=emotion,
            save_path=f"output/{self.current_profile.id}_{time.time()}.wav",
        )
        
        # 播放
        if result.success:
            self._play_audio(result.audio_path)
```

---

## 性能优化

### 推理速度

| 配置 | 推理时间 | 质量 |
|------|---------|------|
| GPU (RTX 3060) | ~200ms/句 | ⭐⭐⭐⭐⭐ |
| GPU (RTX 4090) | ~50ms/句 | ⭐⭐⭐⭐⭐ |
| CPU (i7) | ~3-5s/句 | ⭐⭐⭐⭐ |

**优化建议：**
1. 使用 GPU 推理（CUDA）
2. 启用 `parallel_infer=True`
3. 短文本用 `streaming_mode=True`
4. 长文本用 `text_split_method="cut5"`

### 内存占用

- 基础模型：~2GB
- 推理峰值：~4GB
- 多角色切换：无需额外内存（共享模型）

---

## 常见问题

### Q1: `ConnectionError: 无法连接到服务`
**A:** 确保 GPT-SoVITS 服务已启动：
```bash
python api_v2.py --host 127.0.0.1 --port 9880
```

### Q2: 合成声音不像角色
**A:** 
1. 参考音频质量不够（需要清晰、无背景音乐）
2. 参考音频太短（至少 1 分钟）
3. 文字与参考音频声调差异太大
4. 尝试调整 `temperature` 参数（降低随机性）

### Q3: 中文发音不标准
**A:** 
1. 确保 `text_lang="zh"`
2. 参考音频用中文
3. 检查文本是否有生僻字/多音字

### Q4: 推理速度太慢
**A:** 
1. 使用 GPU
2. 启用 `streaming_mode=True`
3. 减少 `batch_size`
4. 检查 GPU 显存是否充足

---

## 下一步开发

| 优先级 | 功能 | 预计时间 |
|--------|------|---------|
| P0 | 角色声音配置文件管理 | 1 小时 |
| P1 | 与 CharacterProfile 集成 | 1 小时 |
| P2 | 情感 - 人格联动（高神经质→情绪波动） | 1 小时 |
| P3 | 流式播放（边生成边播放） | 2 小时 |
| P4 | 多角色声音切换 | 1 小时 |

---

## 资源链接

- **GPT-SoVITS 仓库**: https://github.com/RVC-Boss/GPT-SoVITS
- **安装教程**: https://github.com/RVC-Boss/GPT-SoVITS/blob/main/docs/cn/README.md
- **API 文档**: https://github.com/RVC-Boss/GPT-SoVITS/wiki/API-Docs
- **示例音频**: https://github.com/RVC-Boss/GPT-SoVITS/tree/main/example
- **讨论区**: https://github.com/RVC-Boss/GPT-SoVITS/discussions

---

## 声音系统架构

```
┌─────────────────────────────────────────────────────────┐
│                    角色系统                              │
│   CharacterProfile.voice → VoiceProfile                 │
└────────────────────┬────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────┐
│                    声音系统                              │
│   GPTSoVITSAdapter                                      │
│   ├─ synthesize()       # 合成语音                      │
│   ├─ clone_voice()      # 克隆声音                      │
│   └─ synthesize_streaming()  # 流式合成                 │
└────────────────────┬────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────┐
│              GPT-SoVITS 推理服务                         │
│   http://127.0.0.1:9880                                 │
│   ├─ /tts          # 合成接口                           │
│   ├─ /ping         # 健康检查                           │
│   └─ /change_*     # 切换模型/情感                      │
└─────────────────────────────────────────────────────────┘
```

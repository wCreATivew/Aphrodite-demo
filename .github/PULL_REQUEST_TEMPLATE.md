# Pull Request Template

## 变更类型

- [x] ✨ 新功能
- [ ] 🐛 Bug 修复
- [ ] 📝 文档更新
- [ ] ♻️ 代码重构
- [ ] ⚡️ 性能优化
- [ ] 🔧 配置变更

## 变更说明

### 新增模块

1. **角色生成系统** (`src/character/`)
   - 从用户简短描述生成完整角色设定
   - 人格特质（大五人格）+ 声音 + 语法 + 环境 + 立场
   - 人格 - 记忆联动：根据人格自动配置记忆参数

2. **声音系统** (`src/voice/`)
   - GPT-SoVITS 声音克隆适配器
   - 支持 7 种情感控制
   - 少样本克隆（1-5 分钟音频）

3. **记忆系统** (`src/memory/`)
   - 三层记忆模型：工作/情景/语义
   - SQLite + FAISS 存储与检索
   - 遗忘曲线 + 强化机制
   - 话题熔断机制
   - 人格感知配置

### 核心功能

- ✅ 人格特质自动转换为记忆系统参数
- ✅ 多角色隔离（character_id）
- ✅ 遗忘曲线（可配置半衰期）
- ✅ 记忆强化（见过次数加固）
- ✅ 话题熔断（检测快速转移）

### 测试

- ✅ 丰川祥子角色测试（Mock 模式）
- ✅ 记忆系统测试（独立版本，零依赖）
- ✅ 人格 - 记忆联动验证
- ✅ 遗忘曲线验证

## 技术栈

- **LLM**: Qwen3 / GPT-4
- **向量检索**: Sentence Transformers + FAISS
- **声音克隆**: GPT-SoVITS
- **数据库**: SQLite
- **语言**: Python 3.10+

## 依赖

```bash
# 核心依赖
pip install openai duckduckgo-search

# 向量检索（可选，启用语义检索）
pip install numpy faiss-cpu sentence-transformers

# 声音克隆（可选，启用 TTS）
# 需单独安装 GPT-SoVITS: https://github.com/RVC-Boss/GPT-SoVITS
```

## 快速开始

```bash
# 1. 安装依赖
pip install -r requirements.txt

# 2. 配置 API Key
export DASHSCOPE_API_KEY="your_key"

# 3. 测试角色生成
python3 test_character_sakiko.py

# 4. 测试记忆系统
python3 test_memory_simple.py
```

## 文档

- `FRAMEWORK.md` - 项目整体架构
- `DELIVERY_REPORT.md` - 交付报告
- `src/character/README.md` - 角色系统使用
- `src/character/SETUP.md` - 环境配置
- `src/voice/README.md` - 声音系统使用
- `docs/memory_system_integration.md` - 记忆系统融合方案

## 示例角色：丰川祥子

```python
from src.character import generate_character_from_query

# 生成角色
profile = generate_character_from_query("banG Dream! 里的丰川祥子")

# 人格特质
print(profile.persona.tags)  # ["坚强", "傲娇", "隐藏脆弱", "音乐天才"]

# 记忆配置（根据人格自动调整）
print(profile.memory_config.half_life_days)  # 12 天（符合"不看向过去"）
print(profile.memory_config.idle_threshold_sec)  # 45 秒（内向性格）
```

## 下一步计划

- [ ] 集成到 runtime_engine
- [ ] LLM 提炼语义记忆
- [ ] 关系系统
- [ ] 世界状态系统
- [ ] 前端界面

## 检查清单

- [x] 代码通过测试
- [x] 文档完整
- [x] 依赖说明清晰
- [x] 示例代码可运行
- [ ] 集成到现有系统（下一步）

## 截图/演示

（如有）

---

**关联 Issue:** #1

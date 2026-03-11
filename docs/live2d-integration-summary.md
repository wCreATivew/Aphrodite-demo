# Live2D × AI 角色系统集成 - 快速参考

## 核心映射关系

### 1️⃣ 人格特质 → 表情倾向
```
外向性高 → 笑容更多 (mouthSmile: 0.3-0.8)
宜人性高 → 眉毛柔和 (eyebrowAngle: -0.2-0.3)
神经质高 → 眨眼频繁 (blinkFrequency: 25 次/分)
活力值高 → 身体前倾 (bodyLean: -0.1-0.4)
```

### 2️⃣ 对话情绪 → 实时表情
```
NEUTRAL    → 默认状态，平滑过渡
HAPPY      → 眼睛弯 + 笑容 + 脸颊红晕 (3 秒)
SAD        → 眼神下垂 + 眉毛下压 (4 秒)
EXCITED    → 眼睛大睁 + 身体前倾 (2 秒)
THINKING   → 视线偏移 + 嘴巴闭合 (持续)
LISTENING  → 轻微笑容 + 专注眼神 (持续)
```

### 3️⃣ 语音 → 口型同步
```
音素检测 → 映射表 → ParamMouthOpenY + ParamMouthForm
支持：元音 (a/o/u/i/e) + 辅音 (m/n/p/b/t/d/k/g...)
平滑窗口：10 帧缓冲插值
```

## 配置生成流程

```
AI 角色设定
    │
    ├─→ 模型选择 (性别/年龄/风格/场景匹配)
    ├─→ 服装选择 (休闲/正式/奇幻预设)
    └─→ 贴图生成 (AI 生成定制纹理)
```

## 集成接口

### 核心 API
```typescript
// 创建角色
const character = await manager.createCharacter(profile);

// 设置情绪
character.setEmotion('happy', 0.8);

// 口型同步
character.startLipSync(audioStream);
character.stopLipSync();

// 切换服装
await character.changeCostume('fantasy_mage');
```

### 事件总线
```typescript
// AI 系统发布
eventBus.publish({
  type: 'EMOTION_CHANGED',
  characterId: 'char_001',
  payload: { emotion: 'excited', intensity: 0.9 }
});

// Live2D 层订阅处理
eventBus.subscribe('EMOTION_CHANGED', handler);
```

## 技术栈

| 组件 | 方案 |
|------|------|
| 渲染 | PixiJS + Live2D Cubism SDK |
| TTS | ElevenLabs / Azure |
| 口型 | Rhubarb Lip Sync |
| 贴图生成 | Stable Diffusion API |

## 文件结构

```
docs/
├── live2d-integration-design.md   # 完整设计文档
└── live2d-integration-summary.md  # 本文件 (快速参考)

src/ (待实现)
├── live2d/
│   ├── CharacterManager.ts
│   ├── EmotionMapper.ts
│   ├── LipSyncEngine.ts
│   └── ModelSelector.ts
└── api/
    ├── characters.ts
    └── websocket.ts
```

## 下一步

1. 搭建 Live2D 渲染环境
2. 实现情绪映射引擎
3. 集成语音合成 + 口型同步
4. 构建模型/服装资源库
5. 开发演示应用

---

详细设计见：`live2d-integration-design.md`

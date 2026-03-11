# 情感状态协议 v1.0

## 1. 情感状态数据结构

### 1.1 基础情感类型

```typescript
enum EmotionType {
  JOY = 'joy',         // 开心 😊
  SADNESS = 'sadness', // 悲伤 😢
  ANGER = 'anger',     // 愤怒 😠
  SURPRISE = 'surprise',// 惊讶 😲
  FEAR = 'fear',       // 恐惧 😨
  DISGUST = 'disgust', // 厌恶 🤢
  NEUTRAL = 'neutral', // 中性 😐
  LOVE = 'love',       // 喜爱 😍
  EXCITEMENT = 'excitement', // 兴奋 🤩
  ANXIETY = 'anxiety'  // 焦虑 😰
}
```

### 1.2 情感状态对象

```typescript
interface EmotionState {
  type: EmotionType;           // 情感类型
  intensity: number;           // 强度 (0.0 - 1.0)
  timestamp: number;           // 创建时间戳 (ms)
  duration: number;            // 预期持续时间 (ms)
  decayRate: number;           // 衰减速率 (0.0 - 1.0 per second)
  source: string;              // 触发源 (事件 ID)
  metadata?: Record<string, any>; // 附加元数据
}
```

### 1.3 情感复合状态

```typescript
interface CompositeEmotionState {
  emotions: Map<EmotionType, EmotionState>;  // 当前所有活跃情感
  dominantEmotion: EmotionType | null;        // 主导情感
  overallArousal: number;                     // 整体唤醒度 (0-1)
  overallValence: number;                     // 整体效价 (-1 到 1, -1=负面，1=正面)
  lastUpdate: number;                         // 最后更新时间
}
```

### 1.4 情感衰减模型

```
intensity(t) = initialIntensity * e^(-decayRate * t)

当 intensity < 0.05 时，情感视为消失
```

### 1.5 情感叠加规则

```typescript
interface EmotionBlendRule {
  // 情感兼容性矩阵
  compatibility: Map<string, number>;  // 情感对之间的兼容性 (0-1)
  
  // 冲突解决策略
  conflictResolution: 'dominance' | 'blend' | 'suppress';
  
  // 最大同时情感数量
  maxConcurrentEmotions: number;
}

// 示例兼容性
const COMPATIBILITY_MATRIX = {
  'joy+excitement': 0.95,   // 高度兼容
  'joy+sadness': 0.3,       // 部分兼容 (苦乐参半)
  'anger+love': 0.1,        // 低兼容 (爱恨交织)
  'fear+surprise': 0.8,     // 高度兼容
  'disgust+joy': 0.05,      // 几乎不兼容
};
```

---

## 2. 情感状态机

### 2.1 状态转换图

```
[NEUTRAL] ←→ [JOY]
     ↓         ↓
  [SADNESS]  [EXCITEMENT]
     ↓         ↓
  [ANGER]   [SURPRISE]
     ↓
  [FEAR/DISGUST]
```

### 2.2 触发事件类型

```typescript
enum EventType {
  // 外部刺激
  USER_MESSAGE = 'user_message',
  ENVIRONMENT_CHANGE = 'environment_change',
  TIME_EVENT = 'time_event',      // 定时事件
  MEMORY_RECALL = 'memory_recall', // 记忆触发
  
  // 内部状态
  EMOTION_DECAY = 'emotion_decay',
  MOOD_SHIFT = 'mood_shift',
  THRESHOLD_CROSS = 'threshold_cross',
  
  // 系统事件
  RESET = 'reset',
  CONFIG_CHANGE = 'config_change'
}

interface TriggerEvent {
  id: string;
  type: EventType;
  payload: Record<string, any>;
  timestamp: number;
  priority: number;  // 1-10, 越高越优先
}
```

### 2.3 状态转换规则

```typescript
interface TransitionRule {
  from: EmotionType | '*';
  to: EmotionType;
  trigger: EventType | EventType[];
  conditions: {
    minIntensity?: number;
    maxIntensity?: number;
    requiredContext?: string[];
  };
  effect: {
    setIntensity: number;
    addIntensity?: number;
    duration?: number;
  };
}

// 示例规则
const TRANSITION_RULES: TransitionRule[] = [
  {
    from: '*',
    to: 'surprise',
    trigger: ['user_message', 'environment_change'],
    conditions: { requiredContext: ['unexpected'] },
    effect: { setIntensity: 0.7, duration: 3000 }
  },
  {
    from: 'joy',
    to: 'excitement',
    trigger: 'user_message',
    conditions: { minIntensity: 0.6 },
    effect: { addIntensity: 0.2 }
  },
  {
    from: '*',
    to: 'sadness',
    trigger: 'memory_recall',
    conditions: { requiredContext: ['negative'] },
    effect: { setIntensity: 0.5, duration: 10000 }
  }
];
```

### 2.4 冷却机制

```typescript
interface CooldownConfig {
  emotionType: EmotionType;
  cooldownMs: number;      // 冷却时间
  lastTriggered: number;   // 最后触发时间
  
  // 检查是否可触发
  canTrigger(): boolean {
    return Date.now() - lastTriggered >= cooldownMs;
  }
}

const DEFAULT_COOLDOWNS: Record<EmotionType, number> = {
  [EmotionType.SURPRISE]: 5000,   // 5 秒
  [EmotionType.ANGER]: 30000,     // 30 秒
  [EmotionType.JOY]: 2000,        // 2 秒
  [EmotionType.SADNESS]: 15000,   // 15 秒
  [EmotionType.NEUTRAL]: 0,       // 无冷却
};
```

### 2.5 阈值机制

```typescript
interface ThresholdConfig {
  // 情感触发阈值
  activationThreshold: number;    // 默认 0.3
  // 主导情感阈值
  dominanceThreshold: number;     // 默认 0.5
  // 情感抑制阈值
  suppressionThreshold: number;   // 默认 0.8 (高于此值会抑制其他情感)
}
```

---

## 3. 实验平台架构

### 3.1 系统架构图

```
┌─────────────────────────────────────────────────────────┐
│                    前端展示层                             │
│  ┌─────────────┐ ┌─────────────┐ ┌─────────────────┐   │
│  │  情感条显示  │ │  状态图/时间线 │ │  事件触发面板   │   │
│  └─────────────┘ └─────────────┘ └─────────────────┘   │
└─────────────────────────────────────────────────────────┘
                          ↕ WebSocket/HTTP
┌─────────────────────────────────────────────────────────┐
│                    API 网关层                              │
│  ┌─────────────────────────────────────────────────┐   │
│  │  /api/emotion  /api/events  /api/config        │   │
│  └─────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────┘
                          ↕
┌─────────────────────────────────────────────────────────┐
│                    情感引擎层                             │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  │
│  │  状态管理    │  │  规则引擎    │  │  衰减计算器  │  │
│  └──────────────┘  └──────────────┘  └──────────────┘  │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  │
│  │  事件处理器  │  │  冷却管理    │  │  冲突解决    │  │
│  └──────────────┘  └──────────────┘  └──────────────┘  │
└─────────────────────────────────────────────────────────┘
                          ↕
┌─────────────────────────────────────────────────────────┐
│                    数据存储层                             │
│  ┌──────────────┐  ┌──────────────┐                     │
│  │  状态存储    │  │  事件日志    │                     │
│  └──────────────┘  └──────────────┘                     │
└─────────────────────────────────────────────────────────┘
```

### 3.2 前端组件

```typescript
// 情感条组件
interface EmotionBarProps {
  emotion: EmotionState;
  width: number;
  showLabel: boolean;
}

// 状态图组件
interface StateGraphProps {
  currentState: CompositeEmotionState;
  history: CompositeEmotionState[];
  timeRange: number;  // ms
}

// 时间线组件
interface TimelineProps {
  events: TriggerEvent[];
  emotionChanges: Array<{
    timestamp: number;
    emotion: EmotionType;
    intensity: number;
  }>;
}

// 事件触发面板
interface EventTriggerPanelProps {
  availableEvents: EventType[];
  onTrigger: (event: TriggerEvent) => void;
}
```

### 3.3 后端服务

```typescript
// 情感引擎主类
class EmotionEngine {
  private state: CompositeEmotionState;
  private rules: TransitionRule[];
  private cooldowns: Map<EmotionType, CooldownConfig>;
  private decayInterval: NodeJS.Timeout;
  
  // 核心方法
  triggerEvent(event: TriggerEvent): void;
  updateState(): void;
  getState(): CompositeEmotionState;
  reset(): void;
  loadConfig(config: EngineConfig): void;
}

// 事件总线
class EventBus {
  on(event: EventType, handler: (e: TriggerEvent) => void): void;
  emit(event: TriggerEvent): void;
}
```

---

## 4. 输出接口规范

### 4.1 情感状态读写 API

```typescript
// RESTful API

// 获取当前情感状态
GET /api/emotion/state
Response: {
  success: boolean;
  data: CompositeEmotionState;
}

// 获取特定情感
GET /api/emotion/state/:emotionType
Response: {
  success: boolean;
  data: EmotionState | null;
}

// 手动设置情感 (调试用)
POST /api/emotion/state
Body: {
  type: EmotionType;
  intensity: number;
  duration?: number;
}
Response: {
  success: boolean;
  data: EmotionState;
}

// 清除所有情感
DELETE /api/emotion/state
Response: {
  success: boolean;
}
```

### 4.2 事件触发 API

```typescript
// 触发事件
POST /api/events/trigger
Body: {
  type: EventType;
  payload?: Record<string, any>;
  priority?: number;
}
Response: {
  success: boolean;
  data: {
    eventId: string;
    triggeredEmotions: EmotionType[];
  };
}

// 获取事件历史
GET /api/events/history?limit=50&offset=0
Response: {
  success: boolean;
  data: TriggerEvent[];
  total: number;
}

// WebSocket 实时推送
ws://localhost:3000/api/ws
// 订阅：{"action": "subscribe", "channel": "emotion"}
// 接收：{"type": "emotion_update", "data": {...}}
```

### 4.3 表现层扩展接口

```typescript
// 表现层适配器接口
interface ExpressionAdapter {
  // 初始化
  init(config: AdapterConfig): Promise<void>;
  
  // 更新情感表现
  updateEmotion(state: CompositeEmotionState): void;
  
  // 播放情感动画
  playAnimation(emotion: EmotionType, intensity: number): void;
  
  // 清理
  destroy(): void;
}

// Live2D 适配器示例
class Live2DAdapter implements ExpressionAdapter {
  private model: Live2DModel;
  
  async init(config: AdapterConfig) {
    // 加载 Live2D 模型
    this.model = await loadModel(config.modelPath);
  }
  
  updateEmotion(state: CompositeEmotionState) {
    const dominant = state.dominantEmotion;
    if (dominant) {
      this.model.setExpression(this.mapEmotionToExpression(dominant));
      this.model.setParameter('intensity', state.overallArousal);
    }
  }
  
  private mapEmotionToExpression(emotion: EmotionType): string {
    const mapping = {
      [EmotionType.JOY]: 'exp_smile',
      [EmotionType.SADNESS]: 'exp_sad',
      [EmotionType.ANGER]: 'exp_angry',
      [EmotionType.SURPRISE]: 'exp_surprised',
      // ...
    };
    return mapping[emotion] || 'exp_normal';
  }
}

// VRM 适配器示例
class VRMAdapter implements ExpressionAdapter {
  private vrm: VRM;
  
  updateEmotion(state: CompositeEmotionState) {
    // 更新 VRM 表情混合形状
    this.vrm.expressionManager?.setValue(
      this.mapEmotionToBlendShape(state.dominantEmotion),
      state.overallArousal
    );
  }
}

// 注册表现层
class ExpressionManager {
  private adapters: Map<string, ExpressionAdapter> = new Map();
  
  register(name: string, adapter: ExpressionAdapter): void;
  unregister(name: string): void;
  broadcast(state: CompositeEmotionState): void;
}
```

### 4.4 配置 API

```typescript
// 获取配置
GET /api/config
Response: EngineConfig

// 更新配置
PUT /api/config
Body: Partial<EngineConfig>
Response: { success: boolean; data: EngineConfig; }

// 重置为默认配置
POST /api/config/reset
Response: { success: boolean; }
```

---

## 5. 情感规则配置格式

```json
{
  "version": "1.0",
  "engine": {
    "tickRate": 100,
    "maxConcurrentEmotions": 5,
    "defaultDecayRate": 0.02
  },
  "emotions": {
    "joy": {
      "baseIntensity": 0.5,
      "decayRate": 0.015,
      "defaultDuration": 8000,
      "cooldown": 2000
    },
    "sadness": {
      "baseIntensity": 0.4,
      "decayRate": 0.008,
      "defaultDuration": 15000,
      "cooldown": 15000
    }
  },
  "rules": [
    {
      "id": "praise_triggers_joy",
      "from": "*",
      "to": "joy",
      "trigger": ["user_message"],
      "conditions": {
        "payloadContains": ["praise", "thank", "love"]
      },
      "effect": {
        "addIntensity": 0.3,
        "duration": 8000
      }
    }
  ],
  "expressions": {
    "adapter": "console",
    "config": {}
  }
}
```

---

## 附录 A: 情感强度参考

| 强度范围 | 描述 | 表现 |
|---------|------|------|
| 0.0 - 0.2 | 微弱 | 几乎不可察觉 |
| 0.2 - 0.4 | 轻度 | 轻微表情变化 |
| 0.4 - 0.6 | 中度 | 明显情感表现 |
| 0.6 - 0.8 | 强烈 | 显著情感反应 |
| 0.8 - 1.0 | 极强 | 情感爆发 |

## 附录 B: 效价 - 唤醒度映射

```
效价 (Valence): -1 (负面) ←→ 0 (中性) ←→ 1 (正面)
唤醒度 (Arousal): 0 (平静) ←→ 1 (激动)

情感映射:
- Joy:       效价 +0.8, 唤醒度 +0.6
- Sadness:   效价 -0.7, 唤醒度 -0.4
- Anger:     效价 -0.6, 唤醒度 +0.8
- Fear:      效价 -0.8, 唤醒度 +0.7
- Surprise:  效价 ±0.3, 唤醒度 +0.9
- Neutral:   效价 0.0, 唤醒度 0.1
```

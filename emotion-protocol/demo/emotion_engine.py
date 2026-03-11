#!/usr/bin/env python3
"""
情感状态协议 - 极简演示引擎
Emotion State Protocol - Minimal Demo Engine

功能:
- 情感状态管理
- 事件触发
- 衰减计算
- 控制台可视化
"""

import time
import random
import json
from enum import Enum
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any
from datetime import datetime
import math


# ═══════════════════════════════════════════════════════════════
# 1. 基础数据结构
# ═══════════════════════════════════════════════════════════════

class EmotionType(str, Enum):
    """基础情感类型"""
    JOY = 'joy'           # 😊
    SADNESS = 'sadness'   # 😢
    ANGER = 'anger'       # 😠
    SURPRISE = 'surprise' # 😲
    FEAR = 'fear'         # 😨
    DISGUST = 'disgust'   # 🤢
    NEUTRAL = 'neutral'   # 😐
    LOVE = 'love'         # 😍
    EXCITEMENT = 'excitement'  # 🤩
    ANXIETY = 'anxiety'   # 😰


# 情感 Emoji 映射
EMOTION_EMOJI = {
    EmotionType.JOY: '😊',
    EmotionType.SADNESS: '😢',
    EmotionType.ANGER: '😠',
    EmotionType.SURPRISE: '😲',
    EmotionType.FEAR: '😨',
    EmotionType.DISGUST: '🤢',
    EmotionType.NEUTRAL: '😐',
    EmotionType.LOVE: '😍',
    EmotionType.EXCITEMENT: '🤩',
    EmotionType.ANXIETY: '😰',
}

# 情感名称 (中文)
EMOTION_NAMES = {
    EmotionType.JOY: '开心',
    EmotionType.SADNESS: '悲伤',
    EmotionType.ANGER: '愤怒',
    EmotionType.SURPRISE: '惊讶',
    EmotionType.FEAR: '恐惧',
    EmotionType.DISGUST: '厌恶',
    EmotionType.NEUTRAL: '中性',
    EmotionType.LOVE: '喜爱',
    EmotionType.EXCITEMENT: '兴奋',
    EmotionType.ANXIETY: '焦虑',
}

# 情感效价和唤醒度
EMOTION_VALIENCE_AROUSAL = {
    EmotionType.JOY: (0.8, 0.6),
    EmotionType.SADNESS: (-0.7, -0.4),
    EmotionType.ANGER: (-0.6, 0.8),
    EmotionType.SURPRISE: (0.3, 0.9),
    EmotionType.FEAR: (-0.8, 0.7),
    EmotionType.DISGUST: (-0.9, 0.5),
    EmotionType.NEUTRAL: (0.0, 0.1),
    EmotionType.LOVE: (0.9, 0.5),
    EmotionType.EXCITEMENT: (0.85, 0.9),
    EmotionType.ANXIETY: (-0.5, 0.7),
}


@dataclass
class EmotionState:
    """单个情感状态"""
    type: EmotionType
    intensity: float  # 0.0 - 1.0
    timestamp: float = field(default_factory=time.time)
    duration: float = 10000  # ms
    decay_rate: float = 0.02  # per second
    source: str = ""
    
    def age(self) -> float:
        """获取情感存在时间 (秒)"""
        return time.time() - self.timestamp
    
    def current_intensity(self) -> float:
        """计算当前强度 (考虑衰减)"""
        elapsed = self.age()
        decayed = self.intensity * math.exp(-self.decay_rate * elapsed)
        return max(0.0, decayed)
    
    def is_alive(self) -> bool:
        """检查情感是否还活跃"""
        return self.current_intensity() > 0.05 and \
               (self.duration <= 0 or self.age() * 1000 < self.duration)
    
    def to_dict(self) -> dict:
        return {
            'type': self.type.value,
            'intensity': self.current_intensity(),
            'age': self.age(),
            'emoji': EMOTION_EMOJI[self.type],
        }


@dataclass
class TriggerEvent:
    """触发事件"""
    id: str
    event_type: str
    payload: Dict[str, Any]
    timestamp: float = field(default_factory=time.time)
    priority: int = 5


@dataclass
class CompositeEmotionState:
    """复合情感状态"""
    emotions: Dict[EmotionType, EmotionState] = field(default_factory=dict)
    
    @property
    def dominant_emotion(self) -> Optional[EmotionType]:
        """获取主导情感"""
        active = [(e.type, e.current_intensity()) 
                  for e in self.emotions.values() if e.is_alive()]
        if not active:
            return EmotionType.NEUTRAL
        return max(active, key=lambda x: x[1])[0]
    
    @property
    def overall_arousal(self) -> float:
        """计算整体唤醒度"""
        if not self.emotions:
            return 0.1
        total = 0.0
        weight = 0.0
        for emotion in self.emotions.values():
            if emotion.is_alive():
                intensity = emotion.current_intensity()
                _, arousal = EMOTION_VALIENCE_AROUSAL.get(
                    emotion.type, (0, 0.1)
                )
                total += arousal * intensity
                weight += intensity
        return total / weight if weight > 0 else 0.1
    
    @property
    def overall_valence(self) -> float:
        """计算整体效价"""
        if not self.emotions:
            return 0.0
        total = 0.0
        weight = 0.0
        for emotion in self.emotions.values():
            if emotion.is_alive():
                intensity = emotion.current_intensity()
                valence, _ = EMOTION_VALIENCE_AROUSAL.get(
                    emotion.type, (0, 0.1)
                )
                total += valence * intensity
                weight += intensity
        return total / weight if weight > 0 else 0.0
    
    def get_active_emotions(self) -> List[EmotionState]:
        """获取所有活跃情感"""
        return [e for e in self.emotions.values() if e.is_alive()]
    
    def to_dict(self) -> dict:
        active = self.get_active_emotions()
        return {
            'dominant': self.dominant_emotion.value if self.dominant_emotion else 'neutral',
            'dominant_emoji': EMOTION_EMOJI.get(self.dominant_emotion, '😐'),
            'arousal': self.overall_arousal,
            'valence': self.overall_valence,
            'emotions': [e.to_dict() for e in active],
        }


# ═══════════════════════════════════════════════════════════════
# 2. 情感引擎
# ═══════════════════════════════════════════════════════════════

class EmotionEngine:
    """情感引擎核心"""
    
    def __init__(self):
        self.state = CompositeEmotionState()
        self.event_history: List[TriggerEvent] = []
        self.cooldowns: Dict[EmotionType, float] = {}
        self.config = self._default_config()
        self._load_config()
    
    def _default_config(self) -> dict:
        return {
            'decay_rates': {
                EmotionType.JOY: 0.015,
                EmotionType.SADNESS: 0.008,
                EmotionType.ANGER: 0.012,
                EmotionType.SURPRISE: 0.05,
                EmotionType.FEAR: 0.02,
                EmotionType.DISGUST: 0.015,
                EmotionType.NEUTRAL: 0.0,
                EmotionType.LOVE: 0.01,
                EmotionType.EXCITEMENT: 0.03,
                EmotionType.ANXIETY: 0.025,
            },
            'cooldowns': {
                EmotionType.SURPRISE: 5.0,
                EmotionType.ANGER: 30.0,
                EmotionType.JOY: 2.0,
                EmotionType.SADNESS: 15.0,
            },
            'max_emotions': 5,
            'activation_threshold': 0.3,
        }
    
    def _load_config(self, config_file: Optional[str] = None):
        """加载配置"""
        if config_file:
            try:
                with open(config_file, 'r', encoding='utf-8') as f:
                    user_config = json.load(f)
                    # 合并配置...
            except FileNotFoundError:
                pass
    
    def trigger_event(self, event: TriggerEvent):
        """触发事件"""
        self.event_history.append(event)
        self._process_event(event)
    
    def _process_event(self, event: TriggerEvent):
        """处理事件，更新情感状态"""
        emotion_changes = self._evaluate_event(event)
        
        for emotion_type, intensity_delta in emotion_changes:
            self._modify_emotion(emotion_type, intensity_delta, event.id)
    
    def _evaluate_event(self, event: TriggerEvent) -> List[tuple]:
        """评估事件对情感的影响"""
        changes = []
        event_type = event.event_type
        payload = event.payload
        
        # 简单规则引擎
        if event_type == 'user_message':
            text = payload.get('text', '').lower()
            
            if any(w in text for w in ['开心', '高兴', '好棒', '谢谢', 'love', 'great']):
                changes.append((EmotionType.JOY, 0.4))
            
            if any(w in text for w in ['伤心', '难过', 'sad', 'unhappy']):
                changes.append((EmotionType.SADNESS, 0.3))
            
            if any(w in text for w in ['生气', '愤怒', 'angry', 'mad']):
                changes.append((EmotionType.ANGER, 0.5))
            
            if any(w in text for w in ['惊讶', 'wow', 'surprise', 'unexpected']):
                changes.append((EmotionType.SURPRISE, 0.6))
            
            if any(w in text for w in ['害怕', '恐惧', 'scared', 'fear']):
                changes.append((EmotionType.FEAR, 0.4))
            
            if any(w in text for w in ['爱', 'love', '喜欢', 'like']):
                changes.append((EmotionType.LOVE, 0.5))
        
        elif event_type == 'memory_recall':
            if payload.get('valence', 'neutral') == 'positive':
                changes.append((EmotionType.JOY, 0.3))
            elif payload.get('valence') == 'negative':
                changes.append((EmotionType.SADNESS, 0.4))
        
        elif event_type == 'environment_change':
            if payload.get('unexpected', False):
                changes.append((EmotionType.SURPRISE, 0.5))
        
        elif event_type == 'time_event':
            if payload.get('type') == 'morning':
                changes.append((EmotionType.JOY, 0.2))
            elif payload.get('type') == 'night':
                changes.append((EmotionType.SADNESS, 0.15))
        
        elif event_type == 'debug_set':
            # 调试用：直接设置情感
            emotion_type = EmotionType(payload.get('emotion', 'neutral'))
            intensity = payload.get('intensity', 0.5)
            changes.append((emotion_type, intensity))
        
        return changes
    
    def _modify_emotion(self, emotion_type: EmotionType, 
                       intensity_delta: float, source: str):
        """修改情感状态"""
        # 检查冷却
        cooldown = self.config['cooldowns'].get(emotion_type, 0)
        last_trigger = self.cooldowns.get(emotion_type, 0)
        if time.time() - last_trigger < cooldown:
            return  # 冷却中
        
        # 更新或创建情感
        if emotion_type in self.state.emotions:
            existing = self.state.emotions[emotion_type]
            if existing.is_alive():
                existing.intensity = min(1.0, existing.intensity + intensity_delta)
                existing.timestamp = time.time()
                existing.source = source
            else:
                self._create_emotion(emotion_type, intensity_delta, source)
        else:
            self._create_emotion(emotion_type, intensity_delta, source)
        
        # 更新冷却
        self.cooldowns[emotion_type] = time.time()
        
        # 清理过期情感
        self._cleanup_emotions()
    
    def _create_emotion(self, emotion_type: EmotionType, 
                       intensity: float, source: str):
        """创建新情感"""
        decay_rate = self.config['decay_rates'].get(
            emotion_type, 0.02
        )
        
        self.state.emotions[emotion_type] = EmotionState(
            type=emotion_type,
            intensity=min(1.0, intensity),
            decay_rate=decay_rate,
            source=source,
        )
    
    def _cleanup_emotions(self):
        """清理过期情感"""
        to_remove = [
            e.type for e in self.state.emotions.values() 
            if not e.is_alive()
        ]
        for emotion_type in to_remove:
            del self.state.emotions[emotion_type]
    
    def update(self):
        """更新情感状态 (每帧调用)"""
        self._cleanup_emotions()
    
    def get_state(self) -> CompositeEmotionState:
        """获取当前状态"""
        self.update()
        return self.state
    
    def reset(self):
        """重置所有情感"""
        self.state = CompositeEmotionState()
        self.cooldowns = {}


# ═══════════════════════════════════════════════════════════════
# 3. 可视化输出
# ═══════════════════════════════════════════════════════════════

class ConsoleVisualizer:
    """控制台可视化器"""
    
    @staticmethod
    def render_bar(value: float, width: int = 20, 
                   fill_char: str = '█', empty_char: str = '░') -> str:
        """渲染进度条"""
        filled = int(value * width)
        empty = width - filled
        return fill_char * filled + empty_char * empty
    
    @staticmethod
    def render_emotions(state: CompositeEmotionState):
        """渲染情感状态"""
        print("\n" + "═" * 50)
        print("🎭 情感状态面板")
        print("═" * 50)
        
        # 主导情感
        dominant = state.dominant_emotion
        emoji = EMOTION_EMOJI.get(dominant, '😐')
        name = EMOTION_NAMES.get(dominant, '中性')
        print(f"\n主导情感：{emoji} {name}")
        
        # 效价和唤醒度
        print(f"效价 (Valence):   {ConsoleVisualizer.render_bar((state.overall_valence + 1) / 2)} {state.overall_valence:+.2f}")
        print(f"唤醒度 (Arousal): {ConsoleVisualizer.render_bar(state.overall_arousal)} {state.overall_arousal:.2f}")
        
        # 各情感强度
        print("\n情感强度:")
        active = state.get_active_emotions()
        
        if not active:
            print("  (无活跃情感)")
        else:
            for emotion in sorted(active, key=lambda e: e.current_intensity(), reverse=True):
                intensity = emotion.current_intensity()
                emoji = EMOTION_EMOJI[emotion.type]
                name = EMOTION_NAMES[emotion.type]
                bar = ConsoleVisualizer.render_bar(intensity, width=15)
                age = emotion.age()
                print(f"  {emoji} {name:6s}: {bar} {intensity:.2f} (存在{age:.1f}s)")
        
        print("═" * 50)
    
    @staticmethod
    def render_event(event: TriggerEvent):
        """渲染事件"""
        print(f"\n⚡ 事件触发：{event.event_type}")
        if event.payload:
            print(f"   载荷：{event.payload}")


# ═══════════════════════════════════════════════════════════════
# 4. 交互式演示
# ═══════════════════════════════════════════════════════════════

class InteractiveDemo:
    """交互式演示"""
    
    def __init__(self):
        self.engine = EmotionEngine()
        self.visualizer = ConsoleVisualizer()
        self.running = True
    
    def print_menu(self):
        """打印菜单"""
        print("\n" + "─" * 50)
        print("🎮 情感状态实验平台 - 控制台演示")
        print("─" * 50)
        print("1. 触发：用户消息 (开心)")
        print("2. 触发：用户消息 (悲伤)")
        print("3. 触发：用户消息 (愤怒)")
        print("4. 触发：用户消息 (惊讶)")
        print("5. 触发：用户消息 (喜爱)")
        print("6. 触发：环境变化 (意外)")
        print("7. 触发：记忆回想 (积极)")
        print("8. 触发：记忆回想 (消极)")
        print("9. 自定义消息")
        print("0. 重置所有情感")
        print("r. 刷新显示")
        print("q. 退出")
        print("─" * 50)
    
    def run(self):
        """运行演示"""
        print("\n" + "🎭" * 25)
        print("   情感状态协议 - 极简演示")
        print("🎭" * 25)
        
        while self.running:
            self.visualizer.render_emotions(self.engine.get_state())
            self.print_menu()
            
            choice = input("\n请选择操作 > ").strip().lower()
            
            if choice == '1':
                self._trigger_user_message("今天好开心！")
            elif choice == '2':
                self._trigger_user_message("有点难过...")
            elif choice == '3':
                self._trigger_user_message("我很生气！")
            elif choice == '4':
                self._trigger_user_message("哇！太惊讶了！")
            elif choice == '5':
                self._trigger_user_message("我喜欢你！")
            elif choice == '6':
                self._trigger_environment_change()
            elif choice == '7':
                self._trigger_memory_recall('positive')
            elif choice == '8':
                self._trigger_memory_recall('negative')
            elif choice == '9':
                self._custom_message()
            elif choice == '0':
                self.engine.reset()
                print("\n✅ 已重置所有情感")
            elif choice == 'r':
                continue
            elif choice == 'q':
                self.running = False
                print("\n👋 再见！")
            else:
                print("\n❌ 无效选项")
            
            time.sleep(0.5)
    
    def _trigger_user_message(self, text: str):
        event = TriggerEvent(
            id=f"msg_{int(time.time())}",
            event_type='user_message',
            payload={'text': text},
        )
        self.engine.trigger_event(event)
        self.visualizer.render_event(event)
    
    def _trigger_environment_change(self):
        event = TriggerEvent(
            id=f"env_{int(time.time())}",
            event_type='environment_change',
            payload={'unexpected': True},
        )
        self.engine.trigger_event(event)
        self.visualizer.render_event(event)
    
    def _trigger_memory_recall(self, valence: str):
        event = TriggerEvent(
            id=f"mem_{int(time.time())}",
            event_type='memory_recall',
            payload={'valence': valence},
        )
        self.engine.trigger_event(event)
        self.visualizer.render_event(event)
    
    def _custom_message(self):
        text = input("输入消息内容 > ").strip()
        if text:
            self._trigger_user_message(text)


# ═══════════════════════════════════════════════════════════════
# 5. 自动演示 (用于展示)
# ═══════════════════════════════════════════════════════════════

def auto_demo():
    """自动演示 - 展示情感流转"""
    print("\n" + "🎭" * 25)
    print("   情感状态协议 - 自动演示")
    print("🎭" * 25)
    
    engine = EmotionEngine()
    visualizer = ConsoleVisualizer()
    
    # 演示场景
    scenarios = [
        ("初始状态", None),
        ("收到赞美消息", TriggerEvent("e1", "user_message", {"text": "你太棒了！"})),
        ("等待衰减...", None),
        ("突然的惊喜", TriggerEvent("e2", "environment_change", {"unexpected": True})),
        ("表达喜爱", TriggerEvent("e3", "user_message", {"text": "我爱你"})),
        ("回忆伤心事", TriggerEvent("e4", "memory_recall", {"valence": "negative"})),
        ("等待所有情感衰减...", None),
    ]
    
    for i, (description, event) in enumerate(scenarios):
        print(f"\n{'='*50}")
        print(f"场景 {i+1}: {description}")
        print('='*50)
        
        if event:
            engine.trigger_event(event)
            visualizer.render_event(event)
        
        visualizer.render_emotions(engine.get_state())
        
        if i < len(scenarios) - 1:
            wait_time = 2 if "等待" in description else 1
            print(f"\n(等待 {wait_time} 秒...)")
            time.sleep(wait_time)
    
    print("\n" + "🎭" * 25)
    print("   演示结束")
    print("🎭" * 25)


# ═══════════════════════════════════════════════════════════════
# 主程序
# ═══════════════════════════════════════════════════════════════

if __name__ == '__main__':
    import sys
    
    if len(sys.argv) > 1 and sys.argv[1] == '--auto':
        auto_demo()
    else:
        demo = InteractiveDemo()
        demo.run()

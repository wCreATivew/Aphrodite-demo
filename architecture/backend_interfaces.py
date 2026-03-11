"""
Live2D 对话演示系统 - Python 后端接口定义

此文件包含后端服务的数据模型和接口定义
可直接用于 FastAPI/Flask 项目
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional, List, Dict, Any
from datetime import datetime
import uuid


# ============ 枚举类型 ============

class EmotionType(str, Enum):
    """情感类型"""
    NEUTRAL = 'neutral'
    HAPPY = 'happy'
    SAD = 'sad'
    ANGRY = 'angry'
    SURPRISED = 'surprised'
    SHY = 'shy'
    THINKING = 'thinking'


class MessageType(str, Enum):
    """消息发送者类型"""
    USER = 'user'
    CHARACTER = 'character'


class MessageStatus(str, Enum):
    """消息状态"""
    SENDING = 'sending'
    SENT = 'sent'
    DELIVERED = 'delivered'
    ERROR = 'error'


class AudioFormat(str, Enum):
    """音频格式"""
    PCM = 'pcm'
    MP3 = 'mp3'
    OGG = 'ogg'
    WAV = 'wav'


class WSMessageType(str, Enum):
    """WebSocket 消息类型"""
    # 客户端 → 服务端
    USER_MESSAGE = 'user_message'
    TYPING_START = 'typing_start'
    TYPING_END = 'typing_end'
    PING = 'ping'
    
    # 服务端 → 客户端
    CHARACTER_REPLY = 'character_reply'
    EXPRESSION_UPDATE = 'expression_update'
    MOTION_TRIGGER = 'motion_trigger'
    PONG = 'pong'
    ERROR = 'error'
    SYSTEM_NOTIFICATION = 'system_notification'
    AUDIO_CHUNK = 'audio_chunk'


# ============ 数据模型 ============

@dataclass
class UserMessage:
    """用户消息 (WebSocket)"""
    message_id: str
    content: str
    timestamp: int  # Unix 毫秒时间戳
    session_id: str
    
    @classmethod
    def create(cls, content: str, session_id: str) -> 'UserMessage':
        return cls(
            message_id=str(uuid.uuid4()),
            content=content,
            timestamp=int(datetime.now().timestamp() * 1000),
            session_id=session_id
        )
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'type': WSMessageType.USER_MESSAGE.value,
            'payload': {
                'message_id': self.message_id,
                'content': self.content,
                'timestamp': self.timestamp,
                'session_id': self.session_id,
            }
        }


@dataclass
class CharacterReply:
    """角色回复 (WebSocket)"""
    message_id: str
    content: str
    emotion: EmotionType
    expression_id: str
    motion_id: Optional[str] = None
    timestamp: int = field(default_factory=lambda: int(datetime.now().timestamp() * 1000))
    in_reply_to: str = ''
    
    @classmethod
    def create(
        cls,
        content: str,
        emotion: EmotionType,
        expression_id: str,
        in_reply_to: str,
        motion_id: Optional[str] = None
    ) -> 'CharacterReply':
        return cls(
            message_id=str(uuid.uuid4()),
            content=content,
            emotion=emotion,
            expression_id=expression_id,
            motion_id=motion_id,
            in_reply_to=in_reply_to
        )
    
    def to_dict(self) -> Dict[str, Any]:
        payload = {
            'type': WSMessageType.CHARACTER_REPLY.value,
            'payload': {
                'message_id': self.message_id,
                'content': self.content,
                'emotion': self.emotion.value,
                'expression_id': self.expression_id,
                'timestamp': self.timestamp,
                'in_reply_to': self.in_reply_to,
            }
        }
        if self.motion_id:
            payload['payload']['motion_id'] = self.motion_id
        return payload


@dataclass
class ExpressionUpdate:
    """表情更新 (WebSocket)"""
    expression_id: str
    blend_time: int = 300  # 默认 300ms 过渡
    priority: int = 1      # 1=普通，2=高 (可打断)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'type': WSMessageType.EXPRESSION_UPDATE.value,
            'payload': {
                'expression_id': self.expression_id,
                'blend_time': self.blend_time,
                'priority': self.priority,
            }
        }


@dataclass
class MotionTrigger:
    """动作触发 (WebSocket)"""
    motion_id: str
    loop: bool = False
    duration: Optional[int] = None  # 毫秒
    
    def to_dict(self) -> Dict[str, Any]:
        payload = {
            'type': WSMessageType.MOTION_TRIGGER.value,
            'payload': {
                'motion_id': self.motion_id,
                'loop': self.loop,
            }
        }
        if self.duration:
            payload['payload']['duration'] = self.duration
        return payload


@dataclass
class AudioChunkHeader:
    """音频分块头部"""
    chunk_id: int
    total_chunks: int
    format: AudioFormat = AudioFormat.PCM
    sample_rate: int = 24000
    channels: int = 1
    is_last: bool = False
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'type': WSMessageType.AUDIO_CHUNK.value,
            'chunk_id': self.chunk_id,
            'total_chunks': self.total_chunks,
            'format': self.format.value,
            'sample_rate': self.sample_rate,
            'channels': self.channels,
            'is_last': self.is_last,
        }


@dataclass
class Message:
    """消息数据模型 (数据库存储)"""
    id: str
    session_id: str
    sender: MessageType
    content: str
    timestamp: int
    emotion: Optional[EmotionType] = None
    in_reply_to: Optional[str] = None
    
    @classmethod
    def create(
        cls,
        session_id: str,
        sender: MessageType,
        content: str,
        emotion: Optional[EmotionType] = None,
        in_reply_to: Optional[str] = None
    ) -> 'Message':
        return cls(
            id=str(uuid.uuid4()),
            session_id=session_id,
            sender=sender,
            content=content,
            timestamp=int(datetime.now().timestamp() * 1000),
            emotion=emotion,
            in_reply_to=in_reply_to
        )
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'id': self.id,
            'sender': self.sender.value,
            'content': self.content,
            'timestamp': self.timestamp,
            'emotion': self.emotion.value if self.emotion else None,
            'in_reply_to': self.in_reply_to,
        }


@dataclass
class CharacterConfig:
    """角色配置"""
    character_id: str
    name: str
    model_path: str
    expressions: Dict[str, str]  # {expression_id: file_path}
    motions: Dict[str, str]      # {motion_id: file_path}
    default_emotion: EmotionType
    voice_id: str
    personality: str
    avatar_url: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'character_id': self.character_id,
            'name': self.name,
            'model_path': self.model_path,
            'expressions': self.expressions,
            'motions': self.motions,
            'default_emotion': self.default_emotion.value,
            'voice_id': self.voice_id,
            'personality': self.personality,
            'avatar_url': self.avatar_url,
        }


@dataclass
class MemorySummary:
    """记忆摘要"""
    character_id: str
    user_name: str
    relationship: str
    key_memories: List[str]
    last_interaction: int
    user_preferences: Optional[Dict[str, Any]] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'character_id': self.character_id,
            'user_name': self.user_name,
            'relationship': self.relationship,
            'key_memories': self.key_memories,
            'last_interaction': self.last_interaction,
            'user_preferences': self.user_preferences,
        }


@dataclass
class SessionInfo:
    """会话信息"""
    session_id: str
    character_id: str
    created_at: int
    last_message_at: int
    message_count: int
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'session_id': self.session_id,
            'character_id': self.character_id,
            'created_at': self.created_at,
            'last_message_at': self.last_message_at,
            'message_count': self.message_count,
        }


# ============ API 请求/响应模型 ============

@dataclass
class VoiceSynthesisRequest:
    """语音合成请求"""
    text: str
    voice_id: str
    format: AudioFormat = AudioFormat.PCM
    sample_rate: int = 24000
    speed: float = 1.0
    pitch: float = 1.0
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'text': self.text,
            'voice_id': self.voice_id,
            'format': self.format.value,
            'sample_rate': self.sample_rate,
            'speed': self.speed,
            'pitch': self.pitch,
        }


@dataclass
class APIResponse:
    """通用 API 响应"""
    success: bool
    data: Optional[Any] = None
    error: Optional[Dict[str, str]] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'success': self.success,
            'data': self.data,
            'error': self.error,
        }


# ============ 服务接口定义 ============

class IMemoryService:
    """记忆服务接口"""
    
    async def save_message(self, message: Message) -> None:
        """保存消息到数据库"""
        raise NotImplementedError
    
    async def get_messages(
        self,
        session_id: str,
        limit: int = 50,
        before: Optional[int] = None
    ) -> List[Message]:
        """获取历史消息"""
        raise NotImplementedError
    
    async def get_context(
        self,
        session_id: str,
        limit: int = 10
    ) -> List[Message]:
        """获取对话上下文 (用于 LLM)"""
        raise NotImplementedError
    
    async def get_memory_summary(self, character_id: str) -> MemorySummary:
        """获取记忆摘要"""
        raise NotImplementedError
    
    async def add_memory(
        self,
        character_id: str,
        memory: str,
        importance: int = 1
    ) -> None:
        """添加长期记忆"""
        raise NotImplementedError


class ICharacterService:
    """角色服务接口"""
    
    async def get_character(self, character_id: str) -> CharacterConfig:
        """获取角色配置"""
        raise NotImplementedError
    
    async def get_expression_params(self, expression_id: str) -> Dict[str, Any]:
        """获取表情参数"""
        raise NotImplementedError
    
    async def get_motion_params(self, motion_id: str) -> Dict[str, Any]:
        """获取动作参数"""
        raise NotImplementedError
    
    def map_emotion_to_expression(self, emotion: EmotionType) -> str:
        """将情感映射到表情 ID"""
        raise NotImplementedError


class IVoiceService:
    """语音服务接口 (GPT-SoVITS)"""
    
    async def synthesize(
        self,
        text: str,
        voice_id: str,
        format: AudioFormat = AudioFormat.PCM,
        sample_rate: int = 24000
    ) -> bytes:
        """合成语音 (一次性)"""
        raise NotImplementedError
    
    async def synthesize_streaming(
        self,
        text: str,
        voice_id: str,
        format: AudioFormat = AudioFormat.PCM,
        sample_rate: int = 24000
    ):
        """流式合成语音 (异步生成器)"""
        raise NotImplementedError


class IEmotionAnalyzer:
    """情感分析服务接口"""
    
    async def analyze(self, text: str) -> EmotionType:
        """分析文本情感"""
        raise NotImplementedError
    
    async def analyze_with_context(
        self,
        text: str,
        context: List[Message]
    ) -> EmotionType:
        """结合上下文分析情感"""
        raise NotImplementedError


class ILLMService:
    """LLM 服务接口"""
    
    async def generate_reply(
        self,
        character: CharacterConfig,
        context: List[Message],
        user_message: str
    ) -> str:
        """生成角色回复"""
        raise NotImplementedError
    
    async def analyze_emotion(self, text: str) -> EmotionType:
        """使用 LLM 分析情感"""
        raise NotImplementedError


class IWebSocketHandler:
    """WebSocket 处理器接口"""
    
    async def on_connect(self, websocket) -> None:
        """连接建立"""
        raise NotImplementedError
    
    async def on_disconnect(self, websocket, code: int) -> None:
        """连接断开"""
        raise NotImplementedError
    
    async def on_message(self, websocket, message: Dict[str, Any]) -> None:
        """收到消息"""
        raise NotImplementedError
    
    async def send_message(self, websocket, message: Dict[str, Any]) -> None:
        """发送消息"""
        raise NotImplementedError


# ============ 表情 - 关键词映射 ============

EMOTION_KEYWORDS: Dict[EmotionType, List[str]] = {
    EmotionType.HAPPY: ['开心', '高兴', '哈哈', '笑', '好棒', '喜欢', '愉快', '乐'],
    EmotionType.SAD: ['难过', '伤心', '哭', '遗憾', '抱歉', '悲伤', '失落'],
    EmotionType.ANGRY: ['生气', '讨厌', '烦', '怒', '气', '可恶'],
    EmotionType.SURPRISED: ['惊讶', '哇', '真的吗', '没想到', '吃惊', '咦'],
    EmotionType.SHY: ['害羞', '不好意思', '尴尬', '腼腆'],
    EmotionType.THINKING: ['嗯...', '让我想想', '思考', '想一下', '考虑'],
    EmotionType.NEUTRAL: [],
}


def detect_emotion_by_keywords(text: str) -> Optional[EmotionType]:
    """基于关键词检测情感"""
    for emotion, keywords in EMOTION_KEYWORDS.items():
        if emotion == EmotionType.NEUTRAL:
            continue
        if any(kw in text for kw in keywords):
            return emotion
    return None


# ============ FastAPI 路由示例 ============

"""
# FastAPI 路由示例代码

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.responses import JSONResponse

app = FastAPI()

# HTTP 路由

@app.get("/api/v1/character/{character_id}/config")
async def get_character_config(character_id: str):
    character_service: ICharacterService = ...  # 依赖注入
    try:
        config = await character_service.get_character(character_id)
        return config.to_dict()
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@app.get("/api/v1/sessions/{session_id}/messages")
async def get_messages(
    session_id: str,
    limit: int = 50,
    before: Optional[int] = None
):
    memory_service: IMemoryService = ...
    messages = await memory_service.get_messages(session_id, limit, before)
    return {
        'messages': [m.to_dict() for m in messages],
        'has_more': len(messages) == limit
    }


@app.get("/api/v1/character/{character_id}/memory/summary")
async def get_memory_summary(character_id: str):
    memory_service: IMemoryService = ...
    summary = await memory_service.get_memory_summary(character_id)
    return summary.to_dict()


@app.post("/api/v1/voice/synthesize")
async def synthesize_voice(request: VoiceSynthesisRequest):
    voice_service: IVoiceService = ...
    audio_data = await voice_service.synthesize(
        text=request.text,
        voice_id=request.voice_id,
        format=request.format,
        sample_rate=request.sample_rate
    )
    return Response(
        content=audio_data,
        media_type="audio/wav"
    )


# WebSocket 路由

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    
    handler: IWebSocketHandler = ...
    await handler.on_connect(websocket)
    
    try:
        while True:
            data = await websocket.receive_json()
            await handler.on_message(websocket, data)
    except WebSocketDisconnect:
        await handler.on_disconnect(websocket, 1000)
"""


# ============ 使用示例 ============

"""
# 创建角色回复示例

reply = CharacterReply.create(
    content="你好呀！今天过得怎么样？",
    emotion=EmotionType.HAPPY,
    expression_id="exp_happy",
    in_reply_to="msg_123",
    motion_id="motion_speak"
)

# 转换为 WebSocket 消息
ws_message = reply.to_dict()
# 发送: await websocket.send_json(ws_message)

# 保存消息到数据库示例

message = Message.create(
    session_id="session_456",
    sender=MessageType.CHARACTER,
    content="你好呀！今天过得怎么样？",
    emotion=EmotionType.HAPPY,
    in_reply_to="msg_123"
)

# 保存: await memory_service.save_message(message)
"""

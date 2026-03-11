/**
 * Live2D 对话演示系统 - TypeScript 接口定义
 * 
 * 此文件包含前端与后端通信的完整类型定义
 * 可直接用于 TypeScript 项目
 */

// ============ 基础类型 ============

export type EmotionType = 
  | 'neutral'    // 中性
  | 'happy'      // 开心
  | 'sad'        // 悲伤
  | 'angry'      // 生气
  | 'surprised'  // 惊讶
  | 'shy'        // 害羞
  | 'thinking';  // 思考

export type MessageType = 'user' | 'character';

export type MessageStatus = 'sending' | 'sent' | 'delivered' | 'error';

export type AudioFormat = 'pcm' | 'mp3' | 'ogg' | 'wav';

// ============ WebSocket 消息 ============

/**
 * 客户端 → 服务端：用户发送消息
 */
export interface UserMessage {
  type: 'user_message';
  payload: {
    message_id: string;        // UUID v4
    content: string;           // 消息文本
    timestamp: number;         // Unix 时间戳 (毫秒)
    session_id: string;        // 会话 ID
  };
}

/**
 * 客户端 → 服务端：开始输入 (用于显示"正在输入"状态)
 */
export interface TypingStart {
  type: 'typing_start';
  payload: {
    session_id: string;
  };
}

/**
 * 客户端 → 服务端：结束输入
 */
export interface TypingEnd {
  type: 'typing_end';
  payload: {
    session_id: string;
  };
}

/**
 * 客户端 → 服务端：心跳
 */
export interface Ping {
  type: 'ping';
  payload: {
    timestamp: number;
  };
}

/**
 * 服务端 → 客户端：角色回复
 */
export interface CharacterReply {
  type: 'character_reply';
  payload: {
    message_id: string;        // 回复消息 ID
    content: string;           // 回复文本
    emotion: EmotionType;      // 情感状态
    expression_id: string;     // Live2D 表情 ID
    motion_id?: string;        // Live2D 动作 ID (可选)
    timestamp: number;         // Unix 时间戳 (毫秒)
    in_reply_to: string;       // 回复的原消息 ID
  };
}

/**
 * 服务端 → 客户端：表情更新
 */
export interface ExpressionUpdate {
  type: 'expression_update';
  payload: {
    expression_id: string;     // 表情 ID
    blend_time: number;        // 过渡时间 (毫秒)
    priority: number;          // 优先级 (高优先级可打断当前表情)
  };
}

/**
 * 服务端 → 客户端：动作触发
 */
export interface MotionTrigger {
  type: 'motion_trigger';
  payload: {
    motion_id: string;         // 动作 ID
    loop: boolean;             // 是否循环播放
    duration?: number;         // 持续时间 (毫秒，可选)
  };
}

/**
 * 服务端 → 客户端：音频分块 (二进制消息)
 * 
 * 实际传输格式:
 * - WebSocket 二进制消息
 * - 前 4 字节：JSON 头长度
 * - 接下来 N 字节：JSON 头
 * - 剩余字节：音频数据
 */
export interface AudioChunkHeader {
  type: 'audio_chunk';
  chunk_id: number;            // 当前分块序号 (从 0 开始)
  total_chunks: number;        // 总分块数
  format: AudioFormat;         // 音频格式
  sample_rate: number;         // 采样率 (Hz)
  channels: number;            // 声道数 (1=单声道，2=立体声)
  is_last: boolean;            // 是否为最后一个分块
}

/**
 * 服务端 → 客户端：心跳响应
 */
export interface Pong {
  type: 'pong';
  payload: {
    timestamp: number;         // 客户端发送的时间戳 (回显)
    server_time: number;       // 服务器当前时间 (毫秒)
  };
}

/**
 * 服务端 → 客户端：错误消息
 */
export interface ErrorMessage {
  type: 'error';
  payload: {
    code: string;              // 错误代码
    message: string;           // 错误描述
    details?: Record<string, any>; // 详细错误信息
  };
}

/**
 * 服务端 → 客户端：系统通知
 */
export interface SystemNotification {
  type: 'system_notification';
  payload: {
    level: 'info' | 'warning' | 'error';
    message: string;
    action?: {
      label: string;
      handler: string;         // 前端处理函数名
    };
  };
}

// ============ 联合类型 ============

/**
 * 所有客户端消息类型
 */
export type ClientMessage = 
  | UserMessage 
  | TypingStart 
  | TypingEnd 
  | Ping;

/**
 * 所有服务端消息类型
 */
export type ServerMessage = 
  | CharacterReply 
  | ExpressionUpdate 
  | MotionTrigger 
  | Pong 
  | ErrorMessage 
  | SystemNotification;

/**
 * WebSocket 消息通用结构
 */
export interface WSMessage<T = any> {
  type: string;
  payload: T;
}

// ============ HTTP API 响应类型 ============

/**
 * 角色配置
 */
export interface CharacterConfig {
  character_id: string;
  name: string;
  model_path: string;          // Live2D 模型路径
  expressions: Record<string, string>;  // 表情映射 {id: path}
  motions: Record<string, string>;      // 动作映射 {id: path}
  default_emotion: EmotionType;
  voice_id: string;
  personality: string;         // 角色人格描述
  avatar_url?: string;         // 头像 URL (可选)
}

/**
 * 单条消息
 */
export interface Message {
  id: string;
  sender: MessageType;
  content: string;
  timestamp: number;
  emotion?: EmotionType;       // 仅角色消息有
  audio_url?: string;          // 语音 URL (可选)
  status?: MessageStatus;      // 仅前端使用
}

/**
 * 消息列表响应
 */
export interface MessageListResponse {
  messages: Message[];
  has_more: boolean;
  next_before?: number;        // 下一页的 before 参数
}

/**
 * 记忆摘要
 */
export interface MemorySummary {
  character_id: string;
  user_name: string;
  relationship: string;
  key_memories: string[];
  last_interaction: number;
  user_preferences?: Record<string, any>;  // 用户偏好
}

/**
 * 会话信息
 */
export interface SessionInfo {
  session_id: string;
  character_id: string;
  created_at: number;
  last_message_at: number;
  message_count: number;
}

/**
 * 语音合成请求
 */
export interface VoiceSynthesisRequest {
  text: string;
  voice_id: string;
  format?: AudioFormat;
  sample_rate?: number;
  speed?: number;              // 语速 (0.5-2.0)
  pitch?: number;              // 音高 (0.5-2.0)
}

/**
 * 通用 API 响应
 */
export interface APIResponse<T> {
  success: boolean;
  data?: T;
  error?: {
    code: string;
    message: string;
  };
}

// ============ Live2D 相关类型 ============

/**
 * Live2D 模型配置
 */
export interface Live2DModelConfig {
  model_path: string;
  scale: number;               // 缩放比例
  position: {
    x: number;
    y: number;
  };
  expressions: Record<string, string>;
  motions: Record<string, string>;
  hit_areas: {
    head: { x: number; y: number; radius: number };
    body: { x: number; y: number; radius: number };
  };
}

/**
 * 表情参数
 */
export interface ExpressionParam {
  id: string;
  name: string;
  file: string;                // .exp3.json 文件路径
  fade_in?: number;            // 淡入时间 (ms)
  fade_out?: number;           // 淡出时间 (ms)
}

/**
 * 动作参数
 */
export interface MotionParam {
  id: string;
  name: string;
  file: string;                // .motion3.json 文件路径
  group?: string;              // 动作组
  sound?: string;              // 配套音效
}

// ============ 前端组件 Props 类型 ============

/**
 * 消息气泡组件 Props
 */
export interface MessageBubbleProps {
  message: Message;
  isUser: boolean;
  showAvatar?: boolean;
  showTimestamp?: boolean;
}

/**
 * 输入框组件 Props
 */
export interface ChatInputProps {
  value: string;
  disabled: boolean;
  placeholder?: string;
  onSend: (text: string) => void;
  onTypingStart?: () => void;
  onTypingEnd?: () => void;
}

/**
 * Live2D 画布组件 Props
 */
export interface Live2DCanvasProps {
  modelConfig: Live2DModelConfig;
  currentExpression: string;
  isSpeaking: boolean;
  onModelLoaded?: () => void;
  onTap?: (area: 'head' | 'body') => void;
}

// ============ WebSocket 客户端类 ============

/**
 * WebSocket 连接状态
 */
export enum WSConnectionState {
  CONNECTING = 'connecting',
  CONNECTED = 'connected',
  RECONNECTING = 'reconnecting',
  DISCONNECTED = 'disconnected',
  ERROR = 'error',
}

/**
 * WebSocket 客户端配置
 */
export interface WSClientConfig {
  url: string;
  token: string;
  reconnectAttempts: number;
  reconnectDelay: number;      // 毫秒
  heartbeatInterval: number;   // 毫秒
}

/**
 * WebSocket 客户端事件
 */
export interface WSClientEvents {
  onConnected: () => void;
  onDisconnected: (reason: string) => void;
  onMessage: (message: ServerMessage) => void;
  onError: (error: Error) => void;
  onReconnecting: (attempt: number) => void;
}

// ============ 工具函数类型 ============

/**
 * 消息序列化/反序列化
 */
export interface MessageSerializer {
  serialize: (msg: ClientMessage) => string;
  deserialize: (data: string) => ServerMessage;
  serializeBinary: (header: AudioChunkHeader, data: ArrayBuffer) => ArrayBuffer;
  deserializeBinary: (data: ArrayBuffer) => { header: AudioChunkHeader; audio: ArrayBuffer };
}

/**
 * 音频播放器接口
 */
export interface AudioPlayer {
  play: (stream: ReadableStream<Uint8Array>) => Promise<void>;
  stop: () => void;
  pause: () => void;
  resume: () => void;
  isPlaying: () => boolean;
}

// ============ 导出所有类型 ============

export type {
  ClientMessage,
  ServerMessage,
  WSMessage,
  CharacterConfig,
  Message,
  MessageListResponse,
  MemorySummary,
  SessionInfo,
  VoiceSynthesisRequest,
  APIResponse,
  Live2DModelConfig,
  ExpressionParam,
  MotionParam,
  MessageBubbleProps,
  ChatInputProps,
  Live2DCanvasProps,
  WSClientConfig,
  WSClientEvents,
  MessageSerializer,
  AudioPlayer,
};

# -*- coding: utf-8 -*-
"""
GPT-SoVITS 声音克隆适配器

项目：https://github.com/RVC-Boss/GPT-SoVITS
特点：
- 少样本克隆（1-5 分钟音频即可）
- 支持中文、英文、日文
- 情感控制（开心、悲伤、愤怒等）
- 实时推理

配置步骤：
1. 克隆 GPT-SoVITS 仓库
2. 训练或下载预训练模型
3. 启动推理 API 服务
4. 本适配器通过 HTTP 调用
"""
from __future__ import annotations

import os
import time
import requests
from typing import Optional, Dict, Any, List
from dataclasses import dataclass
from pathlib import Path


@dataclass
class GPTSoVITSConfig:
    """GPT-SoVITS 配置"""
    api_url: str = "http://127.0.0.1:9880"  # 推理服务地址
    text_lang: str = "zh"  # zh/en/ja
    ref_audio_path: str = ""  # 参考音频路径
    ref_text: str = ""  # 参考音频文本
    text_split_method: str = "cut0"  # cut0/cut1/cut2/cut3/cut4/cut5
    batch_size: int = 1
    batch_threshold: float = 0.75
    split_bucket: bool = True
    return_fragment: bool = False
    speed_factor: float = 1.0
    streaming_mode: bool = False  # 流式输出
    seed: int = -1  # -1=随机
    parallel_infer: bool = True
    repetition_penalty: float = 1.35
    top_k: int = 5
    top_p: float = 1.0
    temperature: float = 1.0
    emotion: Optional[str] = None  # happy/sad/angry/fearful/disgusted/surprised/neutral


@dataclass
class TTSResult:
    """TTS 生成结果"""
    success: bool
    audio_path: Optional[str] = None  # 生成的音频路径
    audio_data: Optional[bytes] = None  # 音频二进制数据（流式模式）
    error: Optional[str] = None
    duration_sec: Optional[float] = None  # 音频时长
    inference_time_ms: Optional[float] = None  # 推理耗时
    
    def save(self, path: str) -> bool:
        """保存音频到文件"""
        if not self.audio_data:
            return False
        try:
            with open(path, 'wb') as f:
                f.write(self.audio_data)
            self.audio_path = path
            return True
        except Exception as e:
            self.error = f"保存失败：{e}"
            return False


class GPTSoVITSAdapter:
    """
    GPT-SoVITS TTS 适配器
    
    使用方式：
    1. 启动 GPT-SoVITS 推理服务
       cd /path/to/GPT-SoVITS
       python api_v2.py --host 127.0.0.1 --port 9880
    
    2. 在本项目中使用
       adapter = GPTSoVITSAdapter()
       result = adapter.synthesize("你好，世界", ref_audio_path="reference.wav", ref_text="你好，世界")
    """
    
    def __init__(self, config: Optional[GPTSoVITSConfig] = None):
        self.config = config or GPTSoVITSConfig()
        self.api_url = self.config.api_url.rstrip('/')
        self._check_service()
    
    def _check_service(self) -> bool:
        """检查 GPT-SoVITS 服务是否可用"""
        try:
            response = requests.get(f"{self.api_url}/ping", timeout=2)
            if response.status_code == 200:
                print(f"[GPT-SoVITS] 服务已连接：{self.api_url}")
                return True
        except Exception:
            pass
        
        print(f"[GPT-SoVITS] 警告：服务可能未启动 ({self.api_url})")
        print(f"[GPT-SoVITS] 请先启动推理服务：python api_v2.py --host 127.0.0.1 --port 9880")
        return False
    
    def synthesize(
        self,
        text: str,
        ref_audio_path: Optional[str] = None,
        ref_text: Optional[str] = None,
        emotion: Optional[str] = None,
        save_path: Optional[str] = None,
    ) -> TTSResult:
        """
        合成语音
        
        Args:
            text: 要合成的文本
            ref_audio_path: 参考音频路径（用于声音克隆）
            ref_text: 参考音频文本
            emotion: 情感（happy/sad/angry/fearful/disgusted/surprised/neutral）
            save_path: 保存路径（可选）
        
        Returns:
            TTSResult: 合成结果
        """
        # 构建请求参数
        params = {
            "text": text,
            "text_lang": self.config.text_lang,
            "text_split_method": self.config.text_split_method,
            "batch_size": self.config.batch_size,
            "batch_threshold": self.config.batch_threshold,
            "split_bucket": self.config.split_bucket,
            "return_fragment": self.config.return_fragment,
            "speed_factor": self.config.speed_factor,
            "streaming_mode": self.config.streaming_mode,
            "seed": self.config.seed,
            "parallel_infer": self.config.parallel_infer,
            "repetition_penalty": self.config.repetition_penalty,
            "top_k": self.config.top_k,
            "top_p": self.config.top_p,
            "temperature": self.config.temperature,
        }
        
        # 参考音频（声音克隆关键参数）
        if ref_audio_path:
            params["ref_audio_path"] = ref_audio_path
        elif self.config.ref_audio_path:
            params["ref_audio_path"] = self.config.ref_audio_path
        
        if ref_text:
            params["prompt_text"] = ref_text
        elif self.config.ref_text:
            params["prompt_text"] = self.config.ref_text
        
        # 情感控制
        if emotion:
            params["emotion"] = emotion
        elif self.config.emotion:
            params["emotion"] = self.config.emotion
        
        # 发送请求
        start_time = time.time()
        try:
            response = requests.post(
                f"{self.api_url}/tts",
                json=params,
                timeout=30,
            )
            
            inference_time = (time.time() - start_time) * 1000
            
            if response.status_code == 200:
                # 成功：返回音频数据
                result = TTSResult(
                    success=True,
                    audio_data=response.content,
                    inference_time_ms=inference_time,
                )
                
                # 估算时长（假设 48kHz 16bit）
                if response.content:
                    result.duration_sec = len(response.content) / (48000 * 2)
                
                # 保存到文件
                if save_path:
                    result.save(save_path)
                
                return result
            else:
                return TTSResult(
                    success=False,
                    error=f"API 返回错误：{response.status_code} - {response.text[:200]}",
                    inference_time_ms=inference_time,
                )
                
        except requests.exceptions.Timeout:
            return TTSResult(
                success=False,
                error="请求超时（>30 秒）",
            )
        except requests.exceptions.ConnectionError:
            return TTSResult(
                success=False,
                error=f"无法连接到 GPT-SoVITS 服务：{self.api_url}",
            )
        except Exception as e:
            return TTSResult(
                success=False,
                error=f"生成失败：{str(e)}",
            )
    
    def synthesize_streaming(
        self,
        text: str,
        ref_audio_path: Optional[str] = None,
        ref_text: Optional[str] = None,
    ):
        """
        流式合成（生成器，边生成边播放）
        
        Yields:
            bytes: 音频数据块
        """
        params = {
            "text": text,
            "text_lang": self.config.text_lang,
            "ref_audio_path": ref_audio_path or self.config.ref_audio_path,
            "prompt_text": ref_text or self.config.ref_text,
            "streaming_mode": True,
        }
        
        try:
            response = requests.post(
                f"{self.api_url}/tts",
                json=params,
                timeout=30,
                stream=True,
            )
            
            if response.status_code == 200:
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        yield chunk
            else:
                raise Exception(f"API 错误：{response.status_code}")
                
        except Exception as e:
            print(f"[GPT-SoVITS] 流式合成失败：{e}")
            return
    
    def clone_voice(
        self,
        character_name: str,
        reference_audio: str,
        reference_text: str,
        output_dir: str = "voices",
    ) -> Dict[str, Any]:
        """
        为角色克隆声音（注册参考音频）
        
        Args:
            character_name: 角色名
            reference_audio: 参考音频路径
            reference_text: 参考音频文本
        
        Returns:
            声音配置字典
        """
        os.makedirs(output_dir, exist_ok=True)
        
        # 为角色创建声音配置文件
        voice_config = {
            "character_name": character_name,
            "ref_audio_path": os.path.abspath(reference_audio),
            "ref_text": reference_text,
            "created_at": time.time(),
        }
        
        # 保存配置
        config_path = os.path.join(output_dir, f"{character_name}_voice.json")
        import json
        with open(config_path, 'w', encoding='utf-8') as f:
            json.dump(voice_config, f, ensure_ascii=False, indent=2)
        
        print(f"[GPT-SoVITS] 声音克隆配置已保存：{config_path}")
        
        # 测试合成
        test_text = "你好，我是" + character_name
        result = self.synthesize(
            test_text,
            ref_audio_path=reference_audio,
            ref_text=reference_text,
            save_path=os.path.join(output_dir, f"{character_name}_test.wav"),
        )
        
        if result.success:
            print(f"[GPT-SoVITS] 声音克隆测试成功：{result.audio_path}")
        else:
            print(f"[GPT-SoVITS] 声音克隆测试失败：{result.error}")
        
        return voice_config
    
    def list_available_voices(self, voices_dir: str = "voices") -> List[Dict[str, Any]]:
        """列出所有可用的声音配置"""
        voices = []
        
        if not os.path.exists(voices_dir):
            return voices
        
        import json
        for filename in os.listdir(voices_dir):
            if filename.endswith("_voice.json"):
                config_path = os.path.join(voices_dir, filename)
                try:
                    with open(config_path, 'r', encoding='utf-8') as f:
                        config = json.load(f)
                    voices.append(config)
                except Exception:
                    pass
        
        return voices


# 便捷函数
def create_tts_adapter(api_url: str = "http://127.0.0.1:9880") -> GPTSoVITSAdapter:
    """创建 TTS 适配器"""
    config = GPTSoVITSConfig(api_url=api_url)
    return GPTSoVITSAdapter(config)


def synthesize_with_gptsovits(
    text: str,
    ref_audio: str,
    ref_text: str,
    save_path: str,
    emotion: Optional[str] = None,
) -> TTSResult:
    """
    快速合成语音
    
    Args:
        text: 合成文本
        ref_audio: 参考音频路径
        ref_text: 参考音频文本
        save_path: 保存路径
        emotion: 情感
    
    Returns:
        TTSResult
    """
    adapter = create_tts_adapter()
    return adapter.synthesize(
        text,
        ref_audio_path=ref_audio,
        ref_text=ref_text,
        emotion=emotion,
        save_path=save_path,
    )


# 测试入口
if __name__ == "__main__":
    print("=" * 60)
    print("GPT-SoVITS 适配器测试")
    print("=" * 60)
    
    # 创建适配器
    adapter = create_tts_adapter()
    
    # 检查服务
    if not adapter._check_service():
        print("\n请启动 GPT-SoVITS 服务:")
        print("  cd /path/to/GPT-SoVITS")
        print("  python api_v2.py --host 127.0.0.1 --port 9880")
        exit(1)
    
    # 列出可用声音
    voices = adapter.list_available_voices()
    print(f"\n可用声音：{len(voices)} 个")
    for v in voices:
        print(f"  - {v.get('character_name', 'Unknown')}")
    
    # 测试合成
    print("\n测试合成...")
    result = adapter.synthesize(
        "你好，这是一个测试。",
        save_path="test_output.wav",
    )
    
    if result.success:
        print(f"✓ 合成成功：{result.audio_path}")
        print(f"  时长：{result.duration_sec:.2f}秒")
        print(f"  推理时间：{result.inference_time_ms:.1f}ms")
    else:
        print(f"✗ 合成失败：{result.error}")

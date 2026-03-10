#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
声音合成评测脚本 - GPT-SoVITS TTS 质量评估

评测维度：
1. 性能指标 - 推理延迟、实时率、吞吐量
2. 音质主观评测 - MOS 评分（Mean Opinion Score）
3. 情感准确性 - 情感控制是否到位
4. 克隆相似度 - 合成声音和原声的相似度

使用方式：
    python test_voice_synth_eval.py --ref_audio reference.wav --ref_text "参考文本"
"""
from __future__ import annotations

import argparse
import json
import os
import time
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import List, Optional, Dict, Any
import wave

# 项目根目录
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in os.sys.path:
    os.sys.path.insert(0, str(ROOT))

from src.voice import GPTSoVITSAdapter, GPTSoVITSConfig


@dataclass
class PerformanceMetrics:
    """性能指标"""
    inference_time_ms: float  # 推理耗时（毫秒）
    audio_duration_sec: float  # 音频时长（秒）
    realtime_factor: float  # 实时率（音频时长/推理时间）
    chars_per_second: float  # 字符生成速度（字/秒）
    text_length: int  # 文本长度


@dataclass
class QualityScore:
    """质量评分"""
    mos_score: float  # MOS 评分（1-5 分）
    naturalness: float  # 自然度（1-5 分）
    clarity: float  # 清晰度（1-5 分）
    emotion_accuracy: float  # 情感准确性（1-5 分）
    similarity: float  # 相似度（1-5 分）
    comments: str = ""  # 主观评价


@dataclass
class EvalResult:
    """评测结果"""
    test_id: str
    text: str
    emotion: str
    performance: PerformanceMetrics
    quality: Optional[QualityScore] = None
    success: bool = True
    error: Optional[str] = None


def get_audio_duration(wav_path: str) -> float:
    """获取 WAV 音频时长（秒）"""
    try:
        with wave.open(wav_path, 'rb') as wf:
            frames = wf.getnframes()
            rate = wf.getframerate()
            return frames / float(rate)
    except Exception as e:
        return 0.0


def evaluate_performance(
    text: str,
    inference_time_ms: float,
    audio_duration_sec: float
) -> PerformanceMetrics:
    """评估性能指标"""
    realtime_factor = audio_duration_sec / (inference_time_ms / 1000.0) if inference_time_ms > 0 else 0.0
    chars_per_second = len(text) / (inference_time_ms / 1000.0) if inference_time_ms > 0 else 0.0
    
    return PerformanceMetrics(
        inference_time_ms=round(inference_time_ms, 2),
        audio_duration_sec=round(audio_duration_sec, 2),
        realtime_factor=round(realtime_factor, 3),
        chars_per_second=round(chars_per_second, 2),
        text_length=len(text),
    )


def run_single_test(
    adapter: GPTSoVITSAdapter,
    test_id: str,
    text: str,
    emotion: str,
    output_dir: Path,
    ref_audio_path: str,
    ref_text: str,
) -> EvalResult:
    """运行单次评测"""
    output_path = output_dir / f"{test_id}_{emotion}.wav"
    
    try:
        start_time = time.time()
        
        result = adapter.synthesize(
            text=text,
            emotion=emotion,
            save_path=str(output_path),
            ref_audio_path=ref_audio_path,
            ref_text=ref_text,
        )
        
        inference_time_ms = (time.time() - start_time) * 1000
        
        if not result.success:
            return EvalResult(
                test_id=test_id,
                text=text,
                emotion=emotion,
                performance=PerformanceMetrics(0, 0, 0, 0, len(text)),
                success=False,
                error=result.error,
            )
        
        # 获取音频时长
        audio_duration = get_audio_duration(str(output_path))
        if audio_duration == 0 and result.duration_sec:
            audio_duration = result.duration_sec
        
        performance = evaluate_performance(text, inference_time_ms, audio_duration)
        
        return EvalResult(
            test_id=test_id,
            text=text,
            emotion=emotion,
            performance=performance,
            success=True,
        )
        
    except Exception as e:
        return EvalResult(
            test_id=test_id,
            text=text,
            emotion=emotion,
            performance=PerformanceMetrics(0, 0, 0, 0, len(text)),
            success=False,
            error=str(e),
        )


def generate_test_cases() -> List[Dict[str, str]]:
    """生成测试用例"""
    return [
        # 中性情感 - 日常对话
        {
            "id": "neutral_001",
            "text": "你好，今天过得怎么样？",
            "emotion": "neutral",
        },
        {
            "id": "neutral_002",
            "text": "我已经决定了，不需要再讨论。",
            "emotion": "neutral",
        },
        # 开心情感
        {
            "id": "happy_001",
            "text": "太好了！我们终于成功了！",
            "emotion": "happy",
        },
        {
            "id": "happy_002",
            "text": "今天天气真好，心情也跟着变好了。",
            "emotion": "happy",
        },
        # 悲伤情感
        {
            "id": "sad_001",
            "text": "为什么事情会变成这样...",
            "emotion": "sad",
        },
        {
            "id": "sad_002",
            "text": "有些东西，失去了就再也回不来了。",
            "emotion": "sad",
        },
        # 愤怒情感
        {
            "id": "angry_001",
            "text": "我受够了！不要再说了！",
            "emotion": "angry",
        },
        # 惊讶情感
        {
            "id": "surprised_001",
            "text": "什么？这怎么可能？！",
            "emotion": "surprised",
        },
        # 长文本测试
        {
            "id": "long_001",
            "text": "这是一个长文本测试，用来评估合成系统在较长句子上的表现。"
                    "通常来说，长文本对推理性能和情感一致性有更高的要求。"
                    "我们希望合成出来的声音能够保持自然的语调和节奏。",
            "emotion": "neutral",
        },
    ]


def print_report(results: List[EvalResult], output_path: str):
    """打印评测报告"""
    print("\n" + "=" * 70)
    print("声音合成评测报告")
    print("=" * 70)
    
    # 统计
    total = len(results)
    success = sum(1 for r in results if r.success)
    failed = total - success
    
    print(f"\n【总览】")
    print(f"  测试总数：{total}")
    print(f"  成功：{success}")
    print(f"  失败：{failed}")
    
    if success > 0:
        # 性能统计
        successful_results = [r for r in results if r.success]
        avg_inference = sum(r.performance.inference_time_ms for r in successful_results) / len(successful_results)
        avg_realtime = sum(r.performance.realtime_factor for r in successful_results) / len(successful_results)
        avg_chars_sec = sum(r.performance.chars_per_second for r in successful_results) / len(successful_results)
        
        print(f"\n【性能指标】")
        print(f"  平均推理时间：{avg_inference:.1f} ms")
        print(f"  平均实时率：{avg_realtime:.2f}x (越差>1 越好)")
        print(f"  平均生成速度：{avg_chars_sec:.1f} 字/秒")
        
        # 按情感分组
        print(f"\n【按情感分组】")
        emotion_groups: Dict[str, List[EvalResult]] = {}
        for r in successful_results:
            if r.emotion not in emotion_groups:
                emotion_groups[r.emotion] = []
            emotion_groups[r.emotion].append(r)
        
        for emotion, group in sorted(emotion_groups.items()):
            avg_time = sum(r.performance.inference_time_ms for r in group) / len(group)
            print(f"  {emotion:12s}: {len(group)}条，平均推理 {avg_time:.1f}ms")
        
        # 详细结果
        print(f"\n【详细结果】")
        print(f"{'ID':15s} {'情感':10s} {'推理 (ms)':>10s} {'实时率':>8s} {'时长 (s)':>8s} {'状态':>8s}")
        print("-" * 70)
        for r in results:
            status = "✅" if r.success else f"❌ {r.error}"
            if r.success:
                print(f"{r.test_id:15s} {r.emotion:10s} {r.performance.inference_time_ms:>10.1f} "
                      f"{r.performance.realtime_factor:>8.2f}x {r.performance.audio_duration_sec:>8.2f}s {status}")
            else:
                print(f"{r.test_id:15s} {r.emotion:10s} {'-':>10s} {'-':>8s} {'-':>8s} {status}")
    
    # 保存报告
    report_data = {
        "summary": {
            "total": total,
            "success": success,
            "failed": failed,
        },
        "results": [asdict(r) for r in results],
    }
    
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(report_data, f, ensure_ascii=False, indent=2)
    
    print(f"\n【报告已保存】{output_path}")
    print("=" * 70)


def main():
    parser = argparse.ArgumentParser(description="GPT-SoVITS 声音合成评测")
    parser.add_argument("--api-url", default="http://127.0.0.1:9880", help="GPT-SoVITS API 地址")
    parser.add_argument("--ref-audio", required=True, help="参考音频路径")
    parser.add_argument("--ref-text", required=True, help="参考音频文本")
    parser.add_argument("--output-dir", default="reports/voice_eval", help="输出目录")
    parser.add_argument("--test-cases", help="自定义测试用例 JSON 文件")
    args = parser.parse_args()
    
    # 创建输出目录
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # 检查参考音频
    if not Path(args.ref_audio).exists():
        print(f"❌ 参考音频不存在：{args.ref_audio}")
        return 1
    
    print(f"🎤 GPT-SoVITS 声音合成评测")
    print(f"   API 地址：{args.api_url}")
    print(f"   参考音频：{args.ref_audio}")
    print(f"   参考文本：{args.ref_text}")
    print(f"   输出目录：{output_dir}")
    
    # 初始化适配器
    try:
        config = GPTSoVITSConfig(
            api_url=args.api_url,
            ref_audio_path=args.ref_audio,
            ref_text=args.ref_text,
        )
        adapter = GPTSoVITSAdapter(config)
    except Exception as e:
        print(f"❌ 无法连接 GPT-SoVITS 服务：{e}")
        print(f"   请确保服务已启动：python api_v2.py --host 127.0.0.1 --port 9880")
        return 1
    
    # 加载测试用例
    if args.test_cases:
        with open(args.test_cases, 'r', encoding='utf-8') as f:
            test_cases = json.load(f)
    else:
        test_cases = generate_test_cases()
    
    print(f"\n📋 测试用例：{len(test_cases)}条")
    
    # 运行评测
    results: List[EvalResult] = []
    for i, case in enumerate(test_cases, 1):
        print(f"\n[{i}/{len(test_cases)}] {case['id']} - {case['emotion']}")
        result = run_single_test(
            adapter=adapter,
            test_id=case['id'],
            text=case['text'],
            emotion=case['emotion'],
            output_dir=output_dir,
            ref_audio_path=args.ref_audio,
            ref_text=args.ref_text,
        )
        results.append(result)
        status = "✅" if result.success else f"❌"
        print(f"   {status} {result.performance.inference_time_ms:.1f}ms "
              f"({result.performance.realtime_factor:.2f}x)")
    
    # 生成报告
    report_path = output_dir / "voice_eval_report.json"
    print_report(results, str(report_path))
    
    return 0 if all(r.success for r in results) else 1


if __name__ == "__main__":
    raise SystemExit(main())

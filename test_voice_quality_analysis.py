#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
声音合成质量分析脚本

通过分析音频特征，评估合成音频相对于真人录音（自然语言）的质量。

评测维度：
1. 频谱相似度 - 对比合成音频和参考音频的频谱特征
2. 基频 (F0) 分析 - 音高自然度
3. 能量包络 - 音量变化自然度
4. 频谱质心 - 音色明亮度
5. 零交叉率 - 清浊音特性
6. MFCC 相似度 - 音色整体相似度
7. 信噪比估计 - 背景噪声水平

评分标准：
- 以真人录音为满分 (100 分)
- 合成音频各项指标与真人录音对比
- 最终给出综合质量评分

使用方式：
    python test_voice_quality_analysis.py \
        --reference real_voice.wav \
        --synthesized synth_voice.wav \
        --report reports/voice_quality_report.json
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import List, Optional, Dict, Any, Tuple

import numpy as np

# 音频处理库
try:
    import librosa
    import soundfile as sf
    from scipy import signal
    from scipy.stats import pearsonr
except ImportError as e:
    print(f"❌ 缺少依赖：{e}")
    print("请安装：pip install librosa soundfile scipy numpy")
    sys.exit(1)


@dataclass
class AudioFeatures:
    """音频特征"""
    # 基础信息
    duration_sec: float  # 时长（秒）
    sample_rate: int  # 采样率
    rms_energy: float  # 均方根能量
    
    # 频谱特征
    spectral_centroid_mean: float  # 频谱质心均值
    spectral_centroid_std: float  # 频谱质心标准差
    spectral_bandwidth_mean: float  # 频谱带宽均值
    spectral_rolloff_mean: float  # 频谱滚降点均值
    spectral_contrast_mean: float  # 频谱对比度均值
    
    # 基频特征
    f0_mean: float  # 基频均值 (Hz)
    f0_std: float  # 基频标准差
    f0_min: float  # 基频最小值
    f0_max: float  # 基频最大值
    
    # MFCC 特征
    mfcc_mean: List[float]  # MFCC 均值（13 维）
    mfcc_std: List[float]  # MFCC 标准差
    
    # 其他特征
    zero_crossing_rate_mean: float  # 零交叉率均值
    harmonics_mean: float  # 谐波均值
    percussive_mean: float  # 打击乐成分均值


@dataclass
class FeatureComparison:
    """特征对比结果"""
    feature_name: str
    reference_value: float
    synthesized_value: float
    similarity_score: float  # 0-100
    weight: float  # 权重


@dataclass
class QualityReport:
    """质量报告"""
    # 文件信息
    reference_file: str
    synthesized_file: str
    
    # 各项评分 (0-100)
    spectral_similarity: float  # 频谱相似度
    f0_naturalness: float  # 基频自然度
    energy_envelope: float  # 能量包络相似度
    mfcc_similarity: float  # MFCC 音色相似度
    noise_level: float  # 信噪比评分（越高越好）
    
    # 综合评分
    overall_score: float  # 综合质量评分
    grade: str  # 等级 (S/A/B/C/D)
    
    # 详细分析
    feature_comparisons: List[FeatureComparison]
    comments: List[str]  # 分析意见


def load_audio(file_path: str, target_sr: int = 22050) -> Tuple[np.ndarray, int]:
    """加载音频文件"""
    y, sr = librosa.load(file_path, sr=target_sr)
    return y, sr


def extract_features(audio: np.ndarray, sr: int) -> AudioFeatures:
    """提取音频特征"""
    # 基础信息
    duration = len(audio) / sr
    rms = np.sqrt(np.mean(audio ** 2))
    
    # 频谱特征
    spectral_centroid = librosa.feature.spectral_centroid(y=audio, sr=sr)[0]
    spectral_bandwidth = librosa.feature.spectral_bandwidth(y=audio, sr=sr)[0]
    spectral_rolloff = librosa.feature.spectral_rolloff(y=audio, sr=sr)[0]
    spectral_contrast = librosa.feature.spectral_contrast(y=audio, sr=sr)
    
    # 基频特征 (使用 pyin 方法)
    f0, voiced_flag, voiced_probs = librosa.pyin(
        audio, fmin=librosa.note_to_hz('C2'), fmax=librosa.note_to_hz('C7')
    )
    f0_clean = f0[~np.isnan(f0)]
    
    if len(f0_clean) == 0:
        f0_clean = np.array([0.0])
    
    # MFCC 特征
    mfccs = librosa.feature.mfcc(y=audio, sr=sr, n_mfcc=13)
    mfcc_mean = np.mean(mfccs, axis=1).tolist()
    mfcc_std = np.std(mfccs, axis=1).tolist()
    
    # 谐波和打击乐成分
    harmonics, percussive = librosa.effects.hpss(audio)
    
    # 零交叉率
    zcr = librosa.feature.zero_crossing_rate(audio)[0]
    
    return AudioFeatures(
        duration_sec=round(duration, 3),
        sample_rate=sr,
        rms_energy=round(float(rms), 6),
        
        spectral_centroid_mean=round(float(np.mean(spectral_centroid)), 2),
        spectral_centroid_std=round(float(np.std(spectral_centroid)), 2),
        spectral_bandwidth_mean=round(float(np.mean(spectral_bandwidth)), 2),
        spectral_rolloff_mean=round(float(np.mean(spectral_rolloff)), 2),
        spectral_contrast_mean=round(float(np.mean(spectral_contrast)), 4),
        
        f0_mean=round(float(np.mean(f0_clean)), 2),
        f0_std=round(float(np.std(f0_clean)), 2),
        f0_min=round(float(np.min(f0_clean)), 2),
        f0_max=round(float(np.max(f0_clean)), 2),
        
        mfcc_mean=[round(x, 4) for x in mfcc_mean],
        mfcc_std=[round(x, 4) for x in mfcc_std],
        
        zero_crossing_rate_mean=round(float(np.mean(zcr)), 4),
        harmonics_mean=round(float(np.mean(np.abs(harmonics))), 6),
        percussive_mean=round(float(np.mean(np.abs(percussive))), 6),
    )


def calculate_similarity(ref_val: float, syn_val: float, tolerance: float = 0.2) -> float:
    """
    计算两个值的相似度 (0-100 分)
    
    使用相对误差计算，tolerance 是可接受的相对误差范围
    """
    if ref_val == 0:
        return 100.0 if syn_val == 0 else 0.0
    
    relative_error = abs(syn_val - ref_val) / abs(ref_val)
    
    # 误差在 tolerance 内得满分，超出线性递减
    if relative_error <= tolerance:
        score = 100.0
    else:
        score = max(0, 100.0 * (1 - (relative_error - tolerance) / tolerance))
    
    return round(score, 2)


def compare_mfcc(ref_mfcc_mean: List[float], syn_mfcc_mean: List[float]) -> float:
    """
    比较 MFCC 特征的相似度
    使用余弦相似度
    """
    ref_vec = np.array(ref_mfcc_mean)
    syn_vec = np.array(syn_mfcc_mean)
    
    # 余弦相似度
    cosine_sim = np.dot(ref_vec, syn_vec) / (np.linalg.norm(ref_vec) * np.linalg.norm(syn_vec))
    
    # 转换为 0-100 分
    score = (cosine_sim + 1) / 2 * 100  # 从 [-1, 1] 映射到 [0, 100]
    return round(score, 2)


def compare_spectrograms(ref_audio: np.ndarray, syn_audio: np.ndarray, sr: int) -> float:
    """
    比较频谱图的相似度
    使用梅尔频谱对比
    """
    # 计算梅尔频谱
    ref_mel = librosa.feature.melspectrogram(y=ref_audio, sr=sr)
    syn_mel = librosa.feature.melspectrogram(y=syn_audio, sr=sr)
    
    # 对数压缩
    ref_mel_db = librosa.power_to_db(ref_mel, ref=np.max)
    syn_mel_db = librosa.power_to_db(syn_mel, ref=np.max)
    
    # 计算相关系数
    if ref_mel_db.shape != syn_mel_db.shape:
        # 形状不同则 resize
        min_frames = min(ref_mel_db.shape[1], syn_mel_db.shape[1])
        ref_mel_db = ref_mel_db[:, :min_frames]
        syn_mel_db = syn_mel_db[:, :min_frames]
    
    # 展平后计算相关系数
    ref_flat = ref_mel_db.flatten()
    syn_flat = syn_mel_db.flatten()
    
    if len(ref_flat) != len(syn_flat):
        return 50.0  # 无法比较时给中等分数
    
    correlation, _ = pearsonr(ref_flat, syn_flat)
    
    # 从 [-1, 1] 映射到 [0, 100]
    score = (correlation + 1) / 2 * 100
    return round(max(0, min(100, score)), 2)


def estimate_snr(audio: np.ndarray) -> float:
    """
    估计信噪比 (SNR)
    简单实现：假设静音段为噪声
    """
    # 计算能量
    energy = audio ** 2
    
    # 假设能量最低的 10% 为噪声
    noise_threshold = np.percentile(energy, 10)
    noise_power = np.mean(energy[energy < noise_threshold])
    signal_power = np.mean(energy[energy >= noise_threshold])
    
    if noise_power == 0:
        return 100.0  # 无噪声
    
    snr_db = 10 * np.log10(signal_power / noise_power)
    
    # 转换为 0-100 分（SNR > 30dB 给满分）
    score = min(100, max(0, snr_db * 3.33))
    return round(score, 2)


def analyze_quality(
    reference_path: str,
    synthesized_path: str
) -> QualityReport:
    """分析合成音频质量"""
    
    # 加载音频
    print(f"📂 加载参考音频：{reference_path}")
    ref_audio, ref_sr = load_audio(reference_path)
    
    print(f"📂 加载合成音频：{synthesized_path}")
    syn_audio, syn_sr = load_audio(synthesized_path)
    
    # 提取特征
    print("🔬 提取音频特征...")
    ref_features = extract_features(ref_audio, ref_sr)
    syn_features = extract_features(syn_audio, syn_sr)
    
    # 各项对比
    feature_comparisons: List[FeatureComparison] = []
    
    # 1. 频谱质心相似度（音色明亮度）
    spectral_sim = calculate_similarity(
        ref_features.spectral_centroid_mean,
        syn_features.spectral_centroid_mean,
        tolerance=0.3
    )
    feature_comparisons.append(FeatureComparison(
        feature_name="频谱质心 (音色明亮度)",
        reference_value=ref_features.spectral_centroid_mean,
        synthesized_value=syn_features.spectral_centroid_mean,
        similarity_score=spectral_sim,
        weight=0.15
    ))
    
    # 2. 基频相似度（音高）
    f0_sim = calculate_similarity(
        ref_features.f0_mean,
        syn_features.f0_mean,
        tolerance=0.15
    )
    feature_comparisons.append(FeatureComparison(
        feature_name="基频 F0 (音高)",
        reference_value=ref_features.f0_mean,
        synthesized_value=syn_features.f0_mean,
        similarity_score=f0_sim,
        weight=0.20
    ))
    
    # 3. 基频变化（语调自然度）
    f0_var_sim = calculate_similarity(
        ref_features.f0_std,
        syn_features.f0_std,
        tolerance=0.25
    )
    feature_comparisons.append(FeatureComparison(
        feature_name="基频变化 (语调自然度)",
        reference_value=ref_features.f0_std,
        synthesized_value=syn_features.f0_std,
        similarity_score=f0_var_sim,
        weight=0.15
    ))
    
    # 4. 能量相似度（音量）
    energy_sim = calculate_similarity(
        ref_features.rms_energy,
        syn_features.rms_energy,
        tolerance=0.2
    )
    feature_comparisons.append(FeatureComparison(
        feature_name="RMS 能量 (音量)",
        reference_value=ref_features.rms_energy,
        synthesized_value=syn_features.rms_energy,
        similarity_score=energy_sim,
        weight=0.10
    ))
    
    # 5. MFCC 相似度（整体音色）
    mfcc_sim = compare_mfcc(ref_features.mfcc_mean, syn_features.mfcc_mean)
    feature_comparisons.append(FeatureComparison(
        feature_name="MFCC (整体音色)",
        reference_value=0,  # 向量，不显示具体值
        synthesized_value=0,
        similarity_score=mfcc_sim,
        weight=0.25
    ))
    
    # 6. 频谱图相似度
    spectrogram_sim = compare_spectrograms(ref_audio, syn_audio, ref_sr)
    feature_comparisons.append(FeatureComparison(
        feature_name="梅尔频谱图 (整体相似度)",
        reference_value=0,
        synthesized_value=0,
        similarity_score=spectrogram_sim,
        weight=0.15
    ))
    
    # 7. 信噪比
    snr_score = estimate_snr(syn_audio)
    feature_comparisons.append(FeatureComparison(
        feature_name="信噪比 (噪声水平)",
        reference_value=100,  # 理想无噪声
        synthesized_value=snr_score,
        similarity_score=snr_score,
        weight=0.10
    ))
    
    # 计算加权总分
    overall_score = sum(fc.similarity_score * fc.weight for fc in feature_comparisons)
    overall_score = round(overall_score, 2)
    
    # 等级评定
    if overall_score >= 90:
        grade = "S"
    elif overall_score >= 80:
        grade = "A"
    elif overall_score >= 70:
        grade = "B"
    elif overall_score >= 60:
        grade = "C"
    else:
        grade = "D"
    
    # 生成分析意见
    comments = []
    
    if mfcc_sim >= 85:
        comments.append("✅ 音色还原度优秀，接近真人")
    elif mfcc_sim >= 70:
        comments.append("⚠️ 音色还原度良好，但有改进空间")
    else:
        comments.append("❌ 音色还原度较低，建议优化模型")
    
    if f0_sim >= 85:
        comments.append("✅ 音高准确")
    else:
        comments.append(f"⚠️ 音高偏差较大 (参考:{ref_features.f0_mean:.1f}Hz vs 合成:{syn_features.f0_mean:.1f}Hz)")
    
    if f0_var_sim >= 80:
        comments.append("✅ 语调自然，有情感起伏")
    else:
        comments.append("⚠️ 语调较平淡，缺乏情感变化")
    
    if snr_score >= 80:
        comments.append("✅ 背景噪声控制良好")
    elif snr_score >= 60:
        comments.append("⚠️ 有轻微背景噪声")
    else:
        comments.append("❌ 背景噪声明显，建议降噪处理")
    
    if spectrogram_sim >= 80:
        comments.append("✅ 整体频谱特征接近真人")
    else:
        comments.append("⚠️ 频谱特征与真人有差异")
    
    return QualityReport(
        reference_file=reference_path,
        synthesized_file=synthesized_path,
        spectral_similarity=spectral_sim,
        f0_naturalness=f0_sim,
        energy_envelope=energy_sim,
        mfcc_similarity=mfcc_sim,
        noise_level=snr_score,
        overall_score=overall_score,
        grade=grade,
        feature_comparisons=feature_comparisons,
        comments=comments,
    )


def print_report(report: QualityReport):
    """打印评测报告"""
    print("\n" + "=" * 70)
    print("🎤 声音合成质量分析报告")
    print("=" * 70)
    
    print(f"\n【文件信息】")
    print(f"  参考音频：{report.reference_file}")
    print(f"  合成音频：{report.synthesized_file}")
    
    print(f"\n【综合评分】")
    print(f"  总分：{report.overall_score:.1f} / 100")
    print(f"  等级：{report.grade}")
    
    print(f"\n【各项评分】")
    print(f"  MFCC 音色相似度：{report.mfcc_similarity:.1f} / 100")
    print(f"  基频自然度：{report.f0_naturalness:.1f} / 100")
    print(f"  频谱相似度：{report.spectral_similarity:.1f} / 100")
    print(f"  能量包络相似度：{report.energy_envelope:.1f} / 100")
    print(f"  信噪比：{report.noise_level:.1f} / 100")
    
    print(f"\n【详细特征对比】")
    print(f"{'特征':25s} {'参考值':>12s} {'合成值':>12s} {'相似度':>10s}")
    print("-" * 70)
    for fc in report.feature_comparisons:
        ref_str = f"{fc.reference_value:.2f}" if fc.reference_value != 0 else "向量"
        syn_str = f"{fc.synthesized_value:.2f}" if fc.synthesized_value != 0 else "向量"
        score_str = f"{fc.similarity_score:.1f}"
        print(f"{fc.feature_name:25s} {ref_str:>12s} {syn_str:>12s} {score_str:>10s}")
    
    print(f"\n【分析意见】")
    for comment in report.comments:
        print(f"  {comment}")
    
    print("\n" + "=" * 70)


def main():
    parser = argparse.ArgumentParser(description="声音合成质量分析")
    parser.add_argument("--reference", "-r", required=True, help="参考音频（真人录音）")
    parser.add_argument("--synthesized", "-s", required=True, help="合成音频")
    parser.add_argument("--report", "-o", default="reports/voice_quality_report.json", help="报告输出路径")
    parser.add_argument("--batch", "-b", help="批量测试 JSON 配置文件")
    args = parser.parse_args()
    
    # 检查文件
    if not Path(args.reference).exists():
        print(f"❌ 参考音频不存在：{args.reference}")
        return 1
    
    if not Path(args.synthesized).exists():
        print(f"❌ 合成音频不存在：{args.synthesized}")
        return 1
    
    print(f"🎤 声音合成质量分析")
    print(f"   参考音频：{args.reference}")
    print(f"   合成音频：{args.synthesized}")
    
    # 分析质量
    report = analyze_quality(args.reference, args.synthesized)
    
    # 打印报告
    print_report(report)
    
    # 保存报告
    os.makedirs(os.path.dirname(args.report) or ".", exist_ok=True)
    with open(args.report, 'w', encoding='utf-8') as f:
        json.dump(asdict(report), f, ensure_ascii=False, indent=2)
    
    print(f"\n💾 报告已保存：{args.report}")
    
    return 0 if report.overall_score >= 70 else 1


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
丰川祥子声音质量快速测试

使用 gptsovits_dataset 中的真实音频作为参考，
合成相同文本后对比质量。
"""
import os
import sys
from pathlib import Path

# 路径配置
DATASET_DIR = Path("/mnt/c/Users/1/Aphrodite-demo/gptsovits_dataset/丰川祥子")
WAVS_DIR = DATASET_DIR / "wavs"
LABELS_FILE = DATASET_DIR / "labels.txt"
OUTPUT_DIR = Path("/home/creative/.openclaw/workspace/Aphrodite-demo/reports/voice_eval")

# 确保输出目录存在
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

print("=" * 70)
print("🎤 丰川祥子声音质量测试")
print("=" * 70)

# 读取标签文件
print(f"\n📂 数据集目录：{DATASET_DIR}")
print(f"📂 音频目录：{WAVS_DIR}")
print(f"📄 标签文件：{LABELS_FILE}")

if not LABELS_FILE.exists():
    print(f"❌ 标签文件不存在：{LABELS_FILE}")
    sys.exit(1)

# 读取前 5 个样本
samples = []
with open(LABELS_FILE, 'r', encoding='utf-8') as f:
    for i, line in enumerate(f):
        if i >= 5:  # 只取前 5 个样本
            break
        line = line.strip()
        if not line or '|' not in line:
            continue
        parts = line.split('|', 1)
        if len(parts) != 2:
            continue
        wav_path, text = parts
        wav_path = wav_path.strip()
        text = text.strip()
        
        # 构建完整路径
        full_wav_path = WAVS_DIR / wav_path.replace("wavs/", "")
        
        if full_wav_path.exists():
            samples.append({
                "id": wav_path.split('/')[-1].replace('.wav', ''),
                "wav_path": str(full_wav_path),
                "text": text,
            })
            print(f"\n✅ 样本 {i+1}: {samples[-1]['id']}.wav")
            print(f"   文本：{text[:50]}...")
            print(f"   路径：{full_wav_path}")
        else:
            print(f"\n⚠️  文件不存在：{full_wav_path}")

print(f"\n📋 找到 {len(samples)} 个有效样本")

if len(samples) == 0:
    print("\n❌ 没有找到有效的音频样本")
    sys.exit(1)

# 生成测试命令
print("\n" + "=" * 70)
print("🚀 测试命令")
print("=" * 70)

print("\n使用质量分析脚本测试单个样本：")
print(f"""
cd /home/creative/.openclaw/workspace/Aphrodite-demo

# 首先需要合成音频（需要 GPT-SoVITS 服务运行中）
python3 test_voice_quality_analysis.py \\
  --reference "{samples[0]['wav_path']}" \\
  --synthesized "path/to/synthesized_{samples[0]['id']}.wav" \\
  --report "reports/voice_eval/sample_{samples[0]['id']}_report.json"
""")

print("\n📁 输出目录：" + str(OUTPUT_DIR))
print("\n💡 提示：")
print("1. 确保 GPT-SoVITS 服务已启动")
print("2. 合成与参考音频相同文本的音频")
print("3. 运行质量分析脚本对比")

print("\n" + "=" * 70)
print("✅ 准备完成")
print("=" * 70)

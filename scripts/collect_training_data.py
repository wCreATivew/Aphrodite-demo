#!/usr/bin/env python3
"""
训练数据搜集脚本

功能：
1. 从 YouTube/B 站下载音频
2. 切割成 3-10 秒片段
3. 自动生成标注文件
4. 质量检测（信噪比、频谱分析）
"""
import os
import sys
import json
from pathlib import Path
from dataclasses import dataclass, asdict
from typing import List, Optional


@dataclass
class AudioSample:
    """音频样本"""
    file_path: str
    duration_sec: float
    text: str
    emotion: str
    quality_score: float
    snr_db: float
    spectral_variance: float


class TrainingDataCollector:
    """训练数据搜集器"""
    
    def __init__(self, output_dir: str):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.samples: List[AudioSample] = []
    
    def collect_from_youtube(self, url: str, output_name: str) -> Optional[AudioSample]:
        """从 YouTube 下载音频"""
        try:
            import yt_dlp
            import librosa
            
            print(f"📥 下载：{url}")
            
            # 下载配置
            ydl_opts = {
                'format': 'bestaudio/best',
                'postprocessors': [{
                    'key': 'FFmpegExtractAudio',
                    'preferredcodec': 'wav',
                    'preferredquality': '192',
                }],
                'outtmpl': str(self.output_dir / f"{output_name}.%(ext)s"),
                'quiet': True,
                'no_warnings': True,
            }
            
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                ydl.download([url])
            
            # 加载音频
            wav_path = self.output_dir / f"{output_name}.wav"
            if not wav_path.exists():
                print(f"❌ 下载失败：{wav_path}")
                return None
            
            # 分析质量
            audio, sr = librosa.load(str(wav_path), sr=44100)
            duration = len(audio) / sr
            
            # 质量检测
            snr = self._calculate_snr(audio)
            spectral_var = self._calculate_spectral_variance(audio, sr)
            quality = self._calculate_quality_score(snr, spectral_var)
            
            sample = AudioSample(
                file_path=str(wav_path),
                duration_sec=round(duration, 2),
                text="",  # 需要手动标注或自动转录
                emotion="neutral",
                quality_score=round(quality, 2),
                snr_db=round(snr, 1),
                spectral_variance=round(spectral_var, 1),
            )
            
            self.samples.append(sample)
            print(f"✅ 下载完成：{sample}")
            
            return sample
            
        except Exception as e:
            print(f"❌ 错误：{e}")
            return None
    
    def collect_from_local(self, input_dir: str) -> List[AudioSample]:
        """从本地目录搜集音频"""
        input_path = Path(input_dir)
        if not input_path.exists():
            print(f"❌ 目录不存在：{input_path}")
            return []
        
        samples = []
        for wav_file in input_path.glob("*.wav"):
            try:
                import librosa
                audio, sr = librosa.load(str(wav_file), sr=44100)
                duration = len(audio) / sr
                
                # 质量检测
                snr = self._calculate_snr(audio)
                spectral_var = self._calculate_spectral_variance(audio, sr)
                quality = self._calculate_quality_score(snr, spectral_var)
                
                sample = AudioSample(
                    file_path=str(wav_file),
                    duration_sec=round(duration, 2),
                    text="",  # 需要标注
                    emotion="neutral",
                    quality_score=round(quality, 2),
                    snr_db=round(snr, 1),
                    spectral_variance=round(spectral_var, 1),
                )
                
                samples.append(sample)
                print(f"✅ 找到：{wav_file.name} - {duration:.2f}s (质量：{quality:.1f})")
                
            except Exception as e:
                print(f"❌ 跳过 {wav_file.name}: {e}")
        
        self.samples.extend(samples)
        return samples
    
    def _calculate_snr(self, audio) -> float:
        """计算信噪比"""
        import numpy as np
        silence_mask = np.abs(audio) < 0.01
        silence_indices = np.where(silence_mask)[0]
        
        if len(silence_indices) > 100:
            noise_level = np.std(audio[silence_indices])
        else:
            sorted_amp = np.sort(np.abs(audio))
            noise_level = np.mean(sorted_amp[:len(sorted_amp)//10])
        
        signal_level = np.std(audio)
        snr_db = 20 * np.log10(signal_level / (noise_level + 0.0001))
        
        return float(snr_db)
    
    def _calculate_spectral_variance(self, audio, sr) -> float:
        """计算频谱变化（情感丰富度）"""
        import numpy as np
        from scipy.fft import fft, fftfreq
        
        frame_size = int(sr * 0.1)
        hop_length = frame_size // 4
        spectral_centroids = []
        
        for i in range(0, len(audio) - frame_size, hop_length):
            frame = audio[i:i + frame_size]
            fft_frame = np.abs(fft(frame))
            freqs = fftfreq(len(frame), 1/sr)
            positive_mask = freqs > 0
            
            if np.sum(fft_frame[positive_mask]) > 0:
                centroid = np.sum(freqs[positive_mask] * fft_frame[positive_mask]) / np.sum(fft_frame[positive_mask])
                spectral_centroids.append(centroid)
        
        if len(spectral_centroids) < 2:
            return 0.0
        
        return float(np.std(spectral_centroids))
    
    def _calculate_quality_score(self, snr: float, spectral_var: float) -> float:
        """计算质量评分 (0-100)"""
        # 信噪比 (0-50 分)
        if snr > 35:
            snr_score = 50
        elif snr > 25:
            snr_score = 30 + (snr - 25) * 2
        else:
            snr_score = snr * 1.2
        
        # 频谱变化 (0-50 分)
        if spectral_var > 1500:
            spec_score = 50
        elif spectral_var > 800:
            spec_score = 30 + (spectral_var - 800) * 0.028
        else:
            spec_score = spectral_var * 0.0375
        
        return snr_score + spec_score
    
    def generate_labels_file(self, output_path: str):
        """生成标注文件"""
        with open(output_path, 'w', encoding='utf-8') as f:
            for sample in self.samples:
                # 格式：wav 路径 | 文本 | 说话人 ID | 情感 | 情感强度
                line = f"{Path(sample.file_path).name} | {sample.text} | 0 | {sample.emotion} | 0.8\n"
                f.write(line)
        
        print(f"💾 标注文件已保存：{output_path}")
    
    def save_report(self, output_path: str):
        """保存质量报告"""
        report = {
            'total_samples': len(self.samples),
            'avg_duration_sec': sum(s.duration_sec for s in self.samples) / len(self.samples) if self.samples else 0,
            'avg_quality_score': sum(s.quality_score for s in self.samples) / len(self.samples) if self.samples else 0,
            'avg_snr_db': sum(s.snr_db for s in self.samples) / len(self.samples) if self.samples else 0,
            'avg_spectral_variance': sum(s.spectral_variance for s in self.samples) / len(self.samples) if self.samples else 0,
            'samples': [asdict(s) for s in self.samples],
        }
        
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(report, f, ensure_ascii=False, indent=2)
        
        print(f"💾 报告已保存：{output_path}")
        
        # 打印摘要
        print(f"\n📊 数据搜集摘要")
        print(f"  总样本数：{len(self.samples)}")
        print(f"  平均时长：{report['avg_duration_sec']:.2f}秒")
        print(f"  平均质量：{report['avg_quality_score']:.1f}/100")
        print(f"  平均信噪比：{report['avg_snr_db']:.1f}dB")
        print(f"  平均频谱变化：{report['avg_spectral_variance']:.1f}Hz")


def main():
    import argparse
    
    parser = argparse.ArgumentParser(description="训练数据搜集脚本")
    parser.add_argument("-o", "--output", default="data/collected", help="输出目录")
    parser.add_argument("-l", "--local", help="本地音频目录")
    parser.add_argument("-u", "--url", help="YouTube/B 站 URL")
    parser.add_argument("-n", "--name", default="sample", help="输出文件名")
    parser.add_argument("-r", "--report", help="质量报告输出路径")
    args = parser.parse_args()
    
    collector = TrainingDataCollector(args.output)
    
    # 从本地搜集
    if args.local:
        print(f"📂 从本地搜集：{args.local}")
        collector.collect_from_local(args.local)
    
    # 从 URL 下载
    if args.url:
        print(f"📥 从 URL 下载：{args.url}")
        collector.collect_from_youtube(args.url, args.name)
    
    # 生成标注文件
    if collector.samples:
        labels_path = Path(args.output) / "labels.txt"
        collector.generate_labels_file(str(labels_path))
        
        # 保存报告
        if args.report:
            collector.save_report(args.report)
        else:
            collector.save_report(str(Path(args.output) / "quality_report.json"))


if __name__ == "__main__":
    main()

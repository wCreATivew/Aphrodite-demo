# 丰川祥子语音样本搜集清单

## 🎯 高质量样本来源

### 1. 官方 MV/动画片段

**优先级：⭐⭐⭐⭐⭐**

| 来源 | 类型 | 时长 | 情感 | URL/关键词 |
|------|------|------|------|-----------|
| **BanG Dream! It's MyGO!!!!!** | TV 动画 | 多集 | 多种 | 搜索 "MyGO 丰川祥子" |
| **Ave Mujica 1st LIVE** | 演唱会 | 多首 | 激情 | 搜索 "Ave Mujica 祥子" |
| **CRYCHIC 片段** | 回忆场景 | 多段 | 悲伤/怀念 | 搜索 "CRYCHIC 祥子" |
| **角色歌 MV** | 音乐视频 | 3-5 分钟 | 多种 | 搜索 "丰川祥子 角色歌" |

---

### 2. YouTube 台词剪辑

**优先级：⭐⭐⭐⭐**

**搜索关键词：**
```
丰川祥子 台词集
豊川祥子 セリフ集
Sakiko Togawa lines
祥子 名シーン
祥子 感情表現
```

**推荐频道（示例）：**
- BanG Dream! 官方频道
- 粉丝剪辑频道（搜索 "祥子 剪辑"）

---

### 3. B 站素材

**优先级：⭐⭐⭐⭐**

**搜索关键词：**
```
丰川祥子 台词
丰川祥子 声优
丰川祥子 名场面
Ave Mujica 祥子
```

**推荐 UP 主：**
- BanG Dream 官方
- 粉丝剪辑作者

---

## 📥 下载命令

### YouTube 下载

```bash
# 单个视频
yt-dlp \
  -f "bestaudio/best" \
  --extract-audio \
  --audio-format wav \
  --audio-quality 192K \
  --output "gptsovits_dataset/丰川祥子/raw_downloads/%(title)s.%(ext)s" \
  "https://www.youtube.com/watch?v=VIDEO_ID" \
  --no-playlist

# 播放列表（台词集）
yt-dlp \
  -f "bestaudio/best" \
  --extract-audio \
  --audio-format wav \
  --audio-quality 192K \
  --output "gptsovits_dataset/丰川祥子/raw_downloads/%(title)s.%(ext)s" \
  "https://www.youtube.com/playlist?list=PLAYLIST_ID"
```

### B 站下载

```bash
# B 站视频
yt-dlp \
  -f "bestaudio/best" \
  --extract-audio \
  --audio-format wav \
  --audio-quality 192K \
  --output "gptsovits_dataset/丰川祥子/raw_downloads/%(title)s.%(ext)s" \
  "https://www.bilibili.com/video/BV1xx411c7mD"
```

---

## ✂️ 切割脚本

下载后需要切割成 3-10 秒片段：

```bash
#!/bin/bash
# 自动切割脚本

INPUT_DIR="gptsovits_dataset/丰川祥子/raw_downloads"
OUTPUT_DIR="gptsovits_dataset/丰川祥子/wavs_raw"

mkdir -p "$OUTPUT_DIR"

for wav_file in "$INPUT_DIR"/*.wav; do
    filename=$(basename "$wav_file" .wav)
    
    # 获取时长
    duration=$(ffprobe -v error -show_entries format=duration -of default=noprint_wrappers=1:nokey=1 "$wav_file")
    
    echo "处理：$filename (${duration}s)"
    
    # 每 5 秒切割一段
    segment_num=0
    current_time=0
    
    while (( $(echo "$current_time < $duration" | bc -l) )); do
        output_file="$OUTPUT_DIR/${filename}_seg${segment_num}.wav"
        
        ffmpeg -y \
            -i "$wav_file" \
            -ss "$current_time" \
            -t 5 \
            -ar 44100 \
            -ac 1 \
            "$output_file" \
            -loglevel quiet
        
        current_time=$(echo "$current_time + 5" | bc -l)
        segment_num=$((segment_num + 1))
    done
    
    echo "  切割成 $segment_num 段"
done

echo "✅ 切割完成"
```

---

## 🎯 样本质量要求

### 音频质量
- ✅ 无背景噪声（SNR > 30dB）
- ✅ 无 BGM 干扰（纯人声）
- ✅ 音量适中（-6dB 到 -3dB）
- ✅ 采样率 44100Hz

### 内容质量
- ✅ 台词清晰可辨
- ✅ 情感表达丰富
- ✅ 无呼吸声/爆破音
- ✅ 时长 3-10 秒

### 情感分布
```
平静：30%  (频谱变化 800-1200Hz)
坚定：25%  (频谱变化 1200-1800Hz)
激动：20%  (频谱变化 1500-2500Hz)
悲伤：15%  (频谱变化 1000-1600Hz)
愤怒：10%  (频谱变化 1800-3000Hz)
```

---

## 📊 目标样本量

| 角色 | Tier | 目标数量 | 总时长 | 质量要求 |
|------|------|---------|--------|---------|
| **丰川祥子** | Tier 1 | 100+ 条 | 8-10 分钟 | 高质量（>80 分） |
| **高松灯** | Tier 1 | 100+ 条 | 8-10 分钟 | 高质量（>80 分） |
| **千早爱音** | Tier 2 | 50+ 条 | 4-5 分钟 | 中等质量（>60 分） |
| **长崎素世** | Tier 2 | 50+ 条 | 4-5 分钟 | 中等质量（>60 分） |
| **椎名立希** | Tier 2 | 50+ 条 | 4-5 分钟 | 中等质量（>60 分） |
| **NPC 们** | Tier 3 | 200+ 条 | 15-20 分钟 | 基础质量（>40 分） |

---

## 🚀 立即执行

### Step 1: 下载样本

```bash
cd /home/creative/.openclaw/workspace/Aphrodite-demo

# 创建下载目录
mkdir -p gptsovits_dataset/丰川祥子/raw_downloads

# 搜索并下载（手动替换 VIDEO_ID）
yt-dlp \
  -f "bestaudio/best" \
  --extract-audio \
  --audio-format wav \
  --audio-quality 192K \
  --output "gptsovits_dataset/丰川祥子/raw_downloads/%(title)s.%(ext)s" \
  "https://www.youtube.com/results?search_query=豊川祥子+セリフ集"
```

### Step 2: 质量筛选

```bash
# 运行质量分析
python3 scripts/collect_training_data.py \
  -l gptsovits_dataset/丰川祥子/raw_downloads \
  -o gptsovits_dataset/丰川祥子/analyzed \
  -r reports/sample_quality_report.json

# 查看报告
cat reports/sample_quality_report.json | jq '.samples[] | select(.quality_score > 70)'
```

### Step 3: 手动标注

```bash
# 高质量样本（>70 分）手动标注情感
# 编辑 labels.txt
```

---

**样本搜集是长期工作，建议每天搜集 10-20 条，一周内达到 100+ 条目标。**

_最后更新：2026-03-10_

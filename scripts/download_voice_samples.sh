#!/bin/bash
# 丰川祥子语音样本下载脚本

# 创建输出目录
OUTPUT_DIR="gptsovits_dataset/丰川祥子/raw_downloads"
mkdir -p "$OUTPUT_DIR"

echo "📥 开始下载丰川祥子语音样本..."

# 样本列表（YouTube/B 站视频 ID）
# 这些是高质量的台词剪辑视频
declare -a VIDEO_IDS=(
    # YouTube 样本
    "dQw4w9WgXcQ"  # 示例 ID，需要替换为真实的祥子台词视频
    "abcdefghijk"  # 示例 ID
    # B 站样本（需要 yt-dlp 支持）
    # "BV1xx411c7mD"
)

# 下载函数
download_sample() {
    local video_id=$1
    local output_name=$2
    
    echo "📥 下载：$video_id -> $output_name"
    
    # YouTube 下载
    yt-dlp \
        -f "bestaudio/best" \
        --extract-audio \
        --audio-format wav \
        --audio-quality 192K \
        --output "$OUTPUT_DIR/${output_name}.%(ext)s" \
        "https://www.youtube.com/watch?v=$video_id" \
        --no-playlist \
        --quiet \
        --no-warnings
    
    if [ $? -eq 0 ]; then
        echo "✅ 下载完成：$output_name"
    else
        echo "❌ 下载失败：$output_name"
    fi
}

# 批量下载
for i in "${!VIDEO_IDS[@]}"; do
    download_sample "${VIDEO_IDS[$i]}" "sample_$i"
done

echo ""
echo "📊 下载完成统计："
ls -lh "$OUTPUT_DIR"/*.wav 2>/dev/null | wc -l
echo "个文件"

# 分析质量
echo ""
echo "🔍 质量分析："
python3 scripts/collect_training_data.py \
    -l "$OUTPUT_DIR" \
    -o "$OUTPUT_DIR/analyzed" \
    -r "$OUTPUT_DIR/quality_report.json"

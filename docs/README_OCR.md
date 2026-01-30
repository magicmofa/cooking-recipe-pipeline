# OCR 字幕提取工具 - 面向对象版本

## 概述

将原来的过程式代码改造为**面向对象**的形式，便于在其他Python程序中调用。

核心特性：
- 使用 **Qwen3-VL:8b** 模型进行高精度OCR（优于一般的OCR库）
- 支持软字幕提取（ffmpeg）和硬字幕提取（OCR）
- 智能ROI检测和差值跳帧优化
- 稳定性检测确保准确性

## 类结构

### 1. `SRTUtils` - SRT文件工具类
静态方法集合，用于处理SRT文件操作：
```python
SRTUtils.format_srt_time(seconds)      # 格式化时间
SRTUtils.normalize_text(text)          # 规范化文本
SRTUtils.is_none_text(text)            # 判断空字幕
SRTUtils.merge_adjacent(segments)      # 合并相邻相同字幕
SRTUtils.write_srt(path, segments)     # 写入SRT文件
```

### 2. `SoftSubExtractor` - 软字幕提取器
使用ffmpeg提取视频中的嵌入字幕：
```python
ok = SoftSubExtractor.extract(
    video_path="video.mp4",
    out_srt="output.srt",
    preferred_stream=None  # 可选指定字幕流索引
)
```

### 3. `HardSubExtractor` - 硬字幕提取器
使用Qwen3-VL OCR提取图像中的字幕：
```python
extractor = HardSubExtractor(
    model="qwen3-vl:8b",
    host="http://localhost:11434"
)

extractor.extract(
    video_path="video.mp4",
    out_srt="output.srt",
    interval_ms=500,       # 采样间隔
    stability=2,           # 稳定性参数
    diff_thresh=2.5,       # ROI变化阈值
    roi_str="0,1440,3840,720",  # ROI: x,y,w,h
    min_duration=0.40,     # 最小字幕长度
)
```

### 4. `SubtitleExtractor` - 主提取器
组合软字幕和硬字幕提取：
```python
extractor = SubtitleExtractor(
    ollama_model="qwen3-vl:8b",
    ollama_host="http://localhost:11434"
)

# 自动先尝试软字幕，失败则使用OCR
srt_path = extractor.extract(
    video_path="video.mp4",
    out_srt="output.srt",
    force_ocr=False  # True 则跳过软字幕提取
)
```

## 快速开始

### 1. 基本使用
```python
from ocr import SubtitleExtractor

extractor = SubtitleExtractor()
srt_file = extractor.extract("movie.mp4")
```

### 2. 仅OCR提取
```python
from ocr import HardSubExtractor

extractor = HardSubExtractor()
extractor.extract("movie.mp4", "output.srt")
```

### 3. 仅软字幕提取
```python
from ocr import SoftSubExtractor

ok = SoftSubExtractor.extract("movie.mp4", "output.srt")
if ok:
    print("提取成功")
```

### 4. 自定义参数
```python
extractor = SubtitleExtractor()
extractor.extract(
    video_path="movie.mp4",
    out_srt="output.srt",
    force_ocr=True,           # 强制使用OCR
    interval_ms=1000,         # 每秒采样一次
    stability=3,              # 更严格的稳定性检查
    roi_str="0,720,1920,360", # 在视频底部720x360区域
    min_duration=0.5,         # 字幕最少显示0.5秒
)
```

## 命令行使用

依然支持原来的CLI：
```bash
python ocr.py video.mp4 -o output.srt --model qwen3-vl:8b

# 强制使用OCR
python ocr.py video.mp4 --force-ocr

# 自定义ROI
python ocr.py video.mp4 --roi "0,1440,3840,720"

# 调整参数
python ocr.py video.mp4 --interval-ms 1000 --stability 3
```

## 参数说明

| 参数 | 默认值 | 说明 |
|-----|------|-----|
| `interval_ms` | 500 | OCR采样间隔（毫秒）。值越大处理越快但可能漏掉字幕 |
| `stability` | 2 | 稳定性参数。需要N次连续相同的识别结果才切换字幕 |
| `diff_thresh` | 2.5 | ROI变化检测阈值。低于此值跳过推理（节省时间） |
| `roi_str` | None | 手动指定ROI区域，格式为 "x,y,w,h"，默认自动为底部30% |
| `min_duration` | 0.40 | 最小字幕段长度（秒） |

## 优势

1. **高准确度** - Qwen3-VL多模态大模型比一般OCR库更准确
2. **灵活易用** - 面向对象设计，可在任何Python程序中调用
3. **参数可调** - 可根据具体视频调整参数获得最佳效果
4. **向后兼容** - 原CLI接口完全保留

## 文件说明

- `ocr.py` - 主模块（面向对象版本）
- `ocr_oop.py` - 同`ocr.py`的备份
- `ocr_backup.py` - 原始过程式版本的备份
- `example_usage.py` - 使用示例

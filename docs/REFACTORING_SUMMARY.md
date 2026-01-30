# 改造总结

## 改造内容

将 `ocr.py` 从过程式编程改造为**面向对象**的设计，便于从其他Python程序中调用。

## 核心改变

### 原来（过程式）
```python
# 大量全局函数
def _format_srt_time(seconds): ...
def _normalize_text(t): ...
def ocr_hardsub_to_srt(video_path, out_srt, ...): ...

# 调用方式
ocr_hardsub_to_srt(video_path, out_srt, model, host, ...)
```

### 现在（面向对象）
```python
# 组织成类
class SRTUtils:
    @staticmethod
    def format_srt_time(seconds): ...
    
class HardSubExtractor:
    def __init__(self, model, host): ...
    def extract(self, video_path, out_srt, ...): ...

class SubtitleExtractor:
    def __init__(self, ollama_model, ollama_host): ...
    def extract(self, video_path, ...): ...

# 调用方式
extractor = SubtitleExtractor()
extractor.extract(video_path, out_srt)
```

## 设计原则

1. **单一职责原则**
   - `SRTUtils`: SRT文件操作
   - `SoftSubExtractor`: ffmpeg软字幕提取
   - `HardSubExtractor`: Qwen3-VL OCR提取
   - `SubtitleExtractor`: 组合提取器

2. **依赖注入**
   - 构造函数注入Ollama参数
   - 便于测试和配置

3. **向后兼容**
   - 保留原来的CLI接口
   - 所有原来的参数仍然有效

## 使用对比

### 方式1：在其他Python程序中调用（推荐）
```python
from ocr import SubtitleExtractor

# 创建提取器实例
extractor = SubtitleExtractor(
    ollama_model="qwen3-vl:8b",
    ollama_host="http://localhost:11434"
)

# 提取字幕
srt_file = extractor.extract(
    video_path="movie.mp4",
    force_ocr=False
)
```

### 方式2：命令行（原来的方式仍然有效）
```bash
python ocr.py video.mp4 -o output.srt --force-ocr
```

## 文件结构

```
烹饪/
├── ocr.py              ← 主模块（新的OOP版本）
├── ocr_oop.py          ← 备份
├── ocr_backup.py       ← 原始版本备份
├── example_usage.py    ← 使用示例
└── README_OCR.md       ← 详细文档
```

## 调用示例

### 示例1：最简单的使用
```python
from ocr import SubtitleExtractor

e = SubtitleExtractor()
e.extract("video.mp4")  # 输出为 video.srt
```

### 示例2：指定输出路径
```python
from ocr import SubtitleExtractor

e = SubtitleExtractor()
e.extract("video.mp4", "my_subs.srt")
```

### 示例3：仅使用OCR
```python
from ocr import SubtitleExtractor

e = SubtitleExtractor()
e.extract("video.mp4", force_ocr=True)  # 跳过软字幕提取
```

### 示例4：自定义参数
```python
from ocr import SubtitleExtractor

e = SubtitleExtractor()
e.extract(
    "video.mp4",
    force_ocr=True,
    interval_ms=1000,      # 1秒采样一次
    stability=3,           # 更严格的稳定性要求
    roi_str="0,720,1920,360",  # 自定义区域
)
```

### 示例5：只提取软字幕
```python
from ocr import SoftSubExtractor

ok = SoftSubExtractor.extract("video.mp4", "output.srt")
if not ok:
    print("未找到软字幕")
```

### 示例6：只使用OCR
```python
from ocr import HardSubExtractor

e = HardSubExtractor(model="qwen3-vl:8b")
e.extract("video.mp4", "output.srt")
```

## 优势

✓ **易于集成** - 可直接在其他程序中导入使用
✓ **参数灵活** - 所有参数都可配置
✓ **高准确度** - 保留Qwen3-VL的优秀性能
✓ **向后兼容** - 原CLI完全兼容
✓ **代码清晰** - 逻辑结构更易理解和维护

## 注意事项

1. 需要Ollama服务运行并加载qwen3-vl:8b模型
2. 需要ffmpeg工具用于软字幕提取
3. 所有参数设置后，可重复调用而无需重新创建实例

## 快速开始

```python
from ocr import SubtitleExtractor

# 创建提取器（一次性初始化）
extractor = SubtitleExtractor()

# 提取多个视频
extractor.extract("movie1.mp4", "movie1.srt")
extractor.extract("movie2.mp4", "movie2.srt")
extractor.extract("movie3.mp4", "movie3.srt", force_ocr=True)
```

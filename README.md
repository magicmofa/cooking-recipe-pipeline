# Cooking Recipe Pipeline

一个基于AI的烹饪视频菜谱提取完整流程系统

## 📋 项目简介

这是一个完整的四阶段处理流程，用于从烹饪视频或图片中自动提取和生成详细的菜谱：

1. **阶段一: 初步提取** - 从视频/图片生成初步菜谱
2. **阶段二: 精细化分析** - 分析缺漏，生成截图时间表
3. **阶段三: 视觉补充** - 提取关键帧，生成完整菜谱
4. **阶段四: 最终整合** - 整合所有资料生成完整教程

## 🚀 快速开始

### 环境要求

- Python 3.8+
- Ollama（用于本地 AI 推理）
- FFmpeg（用于视频处理）

### 安装依赖

```bash
pip install -r requirements.txt
```

### 基本使用

```python
from src.main_pipeline import CookingRecipePipeline

# 初始化流程
pipeline = CookingRecipePipeline(folder_path="path/to/your/video/folder")

# 运行完整流程
result = pipeline.run(
    stage1=True,
    stage2=True,
    stage3=True,
    stage4=True
)

# 获取最终结果
final_tutorial = result.get('final_tutorial')
```

## 📁 项目结构

```
cooking-recipe-pipeline/
├── src/                          # 源代码目录
│   ├── main_pipeline.py         # 主流程控制器
│   ├── file_processor.py        # 文件处理模块
│   ├── fine_grained_processor.py # 精细化分析模块
│   ├── frame_clip_pipeline_v2.py # 关键帧提取模块
│   ├── final_tutorial_generator.py # 最终教程生成模块
│   ├── config_cli.py            # 配置命令行工具
│   ├── aicook.py                # AI 烹饪助手
│   ├── ocr.py                   # OCR 识别模块
│   └── ...                      # 其他辅助模块
├── config/                      # 配置文件目录
│   └── config.json              # 主配置文件
├── docs/                        # 文档目录
│   ├── 流程说明.md              # 流程详细说明
│   ├── CONFIG_UPDATE_说明.md    # 配置更新说明
│   └── ...                      # 其他文档
├── tests/                       # 测试目录
├── README.md                    # 项目说明（本文件）
├── .gitignore                   # Git 忽略规则
└── requirements.txt             # 项目依赖
```

## ⚙️ 配置

项目使用 `config/config.json` 进行配置。主要配置项包括：

- **video_processing**: 视频处理参数
- **ai_model**: AI 模型配置（Ollama URL、模型名称等）
- **output**: 输出目录设置
- **processing**: 处理流程控制选项

详细配置说明请参考 [docs/CONFIG_UPDATE_说明.md](docs/CONFIG_UPDATE_说明.md)

## 📚 文档

- [流程说明.md](docs/流程说明.md) - 详细的流程工作原理
- [CONFIG_UPDATE_说明.md](docs/CONFIG_UPDATE_说明.md) - 配置文件更新说明
- [README_OCR.md](docs/README_OCR.md) - OCR 模块文档
- [REFACTORING_SUMMARY.md](docs/REFACTORING_SUMMARY.md) - 重构总结

## 🔧 核心模块

### FileProcessor
处理输入的视频、图片和文本文件

### FineGrainedProcessor
进行精细化分析，识别缺漏内容

### FrameClipPipeline
提取视频关键帧

### FinalTutorialGenerator
生成最终的完整教程

## 📝 使用示例

```python
from src.file_processor import process_video_file

# 处理视频文件
recipe = process_video_file("video.mp4", config=config)
print(recipe)
```

## 🤝 贡献

欢迎提交 Issues 和 Pull Requests！

## 📄 许可证

MIT License

## 👤 作者

Magic

## 📧 联系方式

如有问题，请提交 Issue 或联系作者。

---

**更新时间**: 2026年1月30日

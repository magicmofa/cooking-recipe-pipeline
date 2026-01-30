# 项目设置配置

import os
from pathlib import Path

# 项目根目录
PROJECT_ROOT = Path(__file__).parent.resolve()

# 目录配置
SRC_DIR = PROJECT_ROOT / "src"
CONFIG_DIR = PROJECT_ROOT / "config"
DOCS_DIR = PROJECT_ROOT / "docs"
TESTS_DIR = PROJECT_ROOT / "tests"

# 添加 src 目录到 Python 路径
import sys
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

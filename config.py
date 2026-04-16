"""
项目配置
"""
from pathlib import Path

# 项目根目录
PROJECT_ROOT = Path(__file__).parent

# 数据目录
DATA_DIR = PROJECT_ROOT / "data"
DB_PATH = DATA_DIR / "state.db"
LOG_DIR = DATA_DIR / "logs"
DEFAULT_LOG_FILE = LOG_DIR / "pipeline.log"

# 输入目录（待扫描的 md 文档目录）
INPUT_DIR = PROJECT_ROOT / "input_docs"

# 输出目录
OUTPUT_DIR = PROJECT_ROOT / "output"
OUTPUT_FILE = OUTPUT_DIR / "status.md"

# 确保目录存在
DATA_DIR.mkdir(exist_ok=True)
INPUT_DIR.mkdir(exist_ok=True)
OUTPUT_DIR.mkdir(exist_ok=True)

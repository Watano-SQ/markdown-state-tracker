"""
数据库连接管理
"""
import sqlite3
from pathlib import Path
from typing import Optional
import sys

# 添加项目根目录到 path
sys.path.insert(0, str(Path(__file__).parent.parent))

from config import DB_PATH
from .schema import SCHEMA_SQL


_connection: Optional[sqlite3.Connection] = None


def get_connection() -> sqlite3.Connection:
    """获取数据库连接（单例）"""
    global _connection
    if _connection is None:
        _connection = sqlite3.connect(str(DB_PATH))
        _connection.row_factory = sqlite3.Row
        _connection.execute("PRAGMA foreign_keys = ON")
    return _connection


def init_db(force: bool = False) -> None:
    """初始化数据库 schema
    
    Args:
        force: 如果为 True，删除现有数据库重建
    """
    if force and DB_PATH.exists():
        DB_PATH.unlink()
    
    conn = get_connection()
    conn.executescript(SCHEMA_SQL)
    conn.commit()


def close_connection() -> None:
    """关闭数据库连接"""
    global _connection
    if _connection is not None:
        _connection.close()
        _connection = None

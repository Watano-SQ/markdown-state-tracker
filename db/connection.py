"""
数据库连接管理
"""
import logging
import sqlite3
from pathlib import Path
from typing import Optional
import sys
from time import perf_counter

# 添加项目根目录到 path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app_logging import get_logger, log_event
from config import DB_PATH
from .schema import SCHEMA_SQL


_connection: Optional[sqlite3.Connection] = None
logger = get_logger("db")


def get_connection() -> sqlite3.Connection:
    """获取数据库连接（单例）"""
    global _connection
    if _connection is None:
        start_time = perf_counter()
        _connection = sqlite3.connect(str(DB_PATH))
        _connection.row_factory = sqlite3.Row
        _connection.execute("PRAGMA foreign_keys = ON")
        log_event(
            logger,
            logging.INFO,
            "db_connection_opened",
            "Opened SQLite connection",
            stage="db",
            db_path=DB_PATH,
            duration_ms=(perf_counter() - start_time) * 1000,
        )
    return _connection


def init_db(force: bool = False) -> None:
    """初始化数据库 schema
    
    Args:
        force: 如果为 True，删除现有数据库重建
    """
    start_time = perf_counter()
    removed_existing = False
    if force and DB_PATH.exists():
        DB_PATH.unlink()
        removed_existing = True
    
    conn = get_connection()
    conn.executescript(SCHEMA_SQL)
    conn.commit()
    log_event(
        logger,
        logging.INFO,
        "db_schema_initialized",
        "Initialized database schema",
        stage="db",
        db_path=DB_PATH,
        force=force,
        removed_existing=removed_existing,
        duration_ms=(perf_counter() - start_time) * 1000,
    )


def close_connection() -> None:
    """关闭数据库连接"""
    global _connection
    if _connection is not None:
        log_event(
            logger,
            logging.INFO,
            "db_connection_closed",
            "Closed SQLite connection",
            stage="db",
            db_path=DB_PATH,
        )
        _connection.close()
        _connection = None

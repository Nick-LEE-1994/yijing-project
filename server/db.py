# -*- coding: utf-8 -*-
"""数据库模块 —— pymysql 连接管理 + 建表 + CRUD"""

import pymysql
import json
from datetime import date
from server import config

# ===== 建表 SQL =====
_INIT_SQL = [
    """
    CREATE TABLE IF NOT EXISTS users (
        id INT AUTO_INCREMENT PRIMARY KEY,
        username VARCHAR(50) UNIQUE NOT NULL,
        password_hash VARCHAR(128) NOT NULL,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
    """,
    """
    CREATE TABLE IF NOT EXISTS divinations (
        id INT AUTO_INCREMENT PRIMARY KEY,
        user_id INT NOT NULL,
        question TEXT CHARACTER SET utf8mb4,
        hexagram_data JSON,
        ai_response TEXT CHARACTER SET utf8mb4,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        INDEX idx_user_time (user_id, created_at)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
    """,
    """
    CREATE TABLE IF NOT EXISTS daily_usage (
        id INT AUTO_INCREMENT PRIMARY KEY,
        user_id INT NOT NULL,
        usage_date DATE NOT NULL,
        count INT DEFAULT 0,
        UNIQUE KEY uk_user_date (user_id, usage_date)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
    """,
]


def get_connection():
    """获取一个新的数据库连接"""
    return pymysql.connect(
        host=config.DB_HOST,
        port=config.DB_PORT,
        user=config.DB_USER,
        password=config.DB_PASSWORD,
        database=config.DB_NAME,
        charset=config.DB_CHARSET,
        cursorclass=pymysql.cursors.DictCursor,
        autocommit=True,
        connect_timeout=10,
        read_timeout=10,
        write_timeout=10,
    )


def _ensure_database():
    """确保数据库存在（切换 VPC 后可能丢失）"""
    import pymysql
    conn = pymysql.connect(
        host=config.DB_HOST, port=config.DB_PORT,
        user=config.DB_USER, password=config.DB_PASSWORD,
        charset=config.DB_CHARSET,
        connect_timeout=10, read_timeout=10, write_timeout=10, autocommit=True,
    )
    try:
        with conn.cursor() as cur:
            cur.execute(
                f"CREATE DATABASE IF NOT EXISTS `{config.DB_NAME}` "
                f"CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci"
            )
        print(f"数据库 '{config.DB_NAME}' 已就绪")
    finally:
        conn.close()


def init_db():
    """建表（首次部署运行一次）"""
    _ensure_database()
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            for sql in _INIT_SQL:
                cur.execute(sql)
        print("数据库表初始化完成")
    finally:
        conn.close()


# ===== 用户相关 =====

def get_user_by_username(username):
    """按用户名查找用户"""
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM users WHERE username = %s", (username,))
            return cur.fetchone()
    finally:
        conn.close()


def get_user_by_id(user_id):
    """按 ID 查找用户"""
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT id, username, created_at FROM users WHERE id = %s", (user_id,))
            return cur.fetchone()
    finally:
        conn.close()


def create_user(username, password_hash):
    """创建用户，返回新用户 ID"""
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO users (username, password_hash) VALUES (%s, %s)",
                (username, password_hash),
            )
            return cur.lastrowid
    finally:
        conn.close()


# ===== 每日用量 =====

def get_daily_count(user_id, usage_date=None):
    """获取用户某日的 AI 使用次数"""
    if usage_date is None:
        usage_date = date.today()
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT count FROM daily_usage WHERE user_id = %s AND usage_date = %s",
                (user_id, usage_date),
            )
            row = cur.fetchone()
            return row["count"] if row else 0
    finally:
        conn.close()


def increment_usage(user_id, usage_date=None):
    """增加用户某日使用次数，返回更新后的计数"""
    if usage_date is None:
        usage_date = date.today()
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            # INSERT ... ON DUPLICATE KEY UPDATE 原子操作
            cur.execute(
                """
                INSERT INTO daily_usage (user_id, usage_date, count)
                VALUES (%s, %s, 1)
                ON DUPLICATE KEY UPDATE count = count + 1
                """,
                (user_id, usage_date),
            )
            cur.execute(
                "SELECT count FROM daily_usage WHERE user_id = %s AND usage_date = %s",
                (user_id, usage_date),
            )
            return cur.fetchone()["count"]
    finally:
        conn.close()


# ===== 起卦记录 =====

def save_divination(user_id, question, hexagram_data, ai_response):
    """保存一条起卦记录，返回记录 ID"""
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO divinations (user_id, question, hexagram_data, ai_response)
                VALUES (%s, %s, %s, %s)
                """,
                (user_id, question, json.dumps(hexagram_data, ensure_ascii=False), ai_response),
            )
            return cur.lastrowid
    finally:
        conn.close()


def save_divination_and_increment_usage(user_id, question, hexagram_data, ai_response, usage_date=None):
    """Save divination history and increment daily usage in one transaction."""
    if usage_date is None:
        usage_date = date.today()
    conn = get_connection()
    conn.autocommit(False)
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO divinations (user_id, question, hexagram_data, ai_response)
                VALUES (%s, %s, %s, %s)
                """,
                (user_id, question, json.dumps(hexagram_data, ensure_ascii=False), ai_response),
            )
            record_id = cur.lastrowid

            cur.execute(
                """
                INSERT INTO daily_usage (user_id, usage_date, count)
                VALUES (%s, %s, 1)
                ON DUPLICATE KEY UPDATE count = count + 1
                """,
                (user_id, usage_date),
            )
            cur.execute(
                "SELECT count FROM daily_usage WHERE user_id = %s AND usage_date = %s",
                (user_id, usage_date),
            )
            used_count = cur.fetchone()["count"]
        conn.commit()
        return record_id, used_count
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def get_history(user_id, page=1, page_size=20):
    """获取用户起卦历史（分页），返回 (records, total)"""
    offset = (page - 1) * page_size
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT COUNT(*) as total FROM divinations WHERE user_id = %s",
                (user_id,),
            )
            total = cur.fetchone()["total"]

            cur.execute(
                """
                SELECT id, question, created_at
                FROM divinations
                WHERE user_id = %s
                ORDER BY created_at DESC
                LIMIT %s OFFSET %s
                """,
                (user_id, page_size, offset),
            )
            records = cur.fetchall()
            return records, total
    finally:
        conn.close()


def get_divination(div_id, user_id):
    """获取单条起卦详情（需匹配 user_id）"""
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, question, hexagram_data, ai_response, created_at
                FROM divinations
                WHERE id = %s AND user_id = %s
                """,
                (div_id, user_id),
            )
            row = cur.fetchone()
            if row and row["hexagram_data"]:
                row["hexagram_data"] = json.loads(row["hexagram_data"])
            return row
    finally:
        conn.close()

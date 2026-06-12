# -*- coding: utf-8 -*-
"""Runtime configuration for local development and Tencent Cloud SCF.

Production secrets must come from environment variables. Keep this file free of
real cloud keys, API keys, database passwords, and production JWT secrets.
"""

import os


def _env(name, default=""):
    value = os.environ.get(name, default)
    return value.strip() if isinstance(value, str) else value


# ===== DeepSeek AI =====
DEEPSEEK_API_KEY = _env("DEEPSEEK_API_KEY")
DEEPSEEK_BASE_URL = os.environ.get("DEEPSEEK_BASE_URL", "https://api.deepseek.com")
DEEPSEEK_MODEL = os.environ.get("DEEPSEEK_MODEL", "deepseek-v4-flash")

# ===== MySQL / TDSQL-C =====
DB_HOST = os.environ.get("DB_HOST", "127.0.0.1")
DB_PORT = int(os.environ.get("DB_PORT", "3306"))
DB_USER = os.environ.get("DB_USER", "root")
DB_PASSWORD = _env("DB_PASSWORD")
DB_NAME = os.environ.get("DB_NAME", "yijing")
DB_CHARSET = "utf8mb4"

# ===== JWT =====
JWT_SECRET = _env("JWT_SECRET", "dev-only-change-me")
JWT_EXPIRES_DAYS = int(os.environ.get("JWT_EXPIRES_DAYS", "7"))

# ===== CORS =====
# Comma-separated origins. Add the COS static website origin after deployment,
# for example: https://<bucket>.cos-website.ap-chengdu.myqcloud.com
CORS_ORIGINS = [
    origin.strip()
    for origin in os.environ.get("CORS_ORIGINS", "http://localhost:8081").split(",")
    if origin.strip()
]

# ===== Business =====
DAILY_AI_LIMIT = int(os.environ.get("DAILY_AI_LIMIT", "10"))
BUILD_VERSION = os.environ.get("BUILD_VERSION", "public-deploy-20260609")

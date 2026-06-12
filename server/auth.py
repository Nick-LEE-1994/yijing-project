# -*- coding: utf-8 -*-
"""认证模块 —— 密码哈希 + JWT 签发/验证 + require_auth 装饰器"""

import functools
from datetime import datetime, timedelta, timezone

import jwt
from werkzeug.security import generate_password_hash, check_password_hash

from server import config


# ===== 密码 =====

def hash_password(plain: str) -> str:
    """生成密码哈希"""
    return generate_password_hash(plain)


def verify_password(plain: str, hashed: str) -> bool:
    """验证密码"""
    return check_password_hash(hashed, plain)


# ===== JWT =====

def create_token(user_id: int, username: str) -> str:
    """签发 JWT token"""
    payload = {
        "user_id": user_id,
        "username": username,
        "exp": datetime.now(timezone.utc) + timedelta(days=config.JWT_EXPIRES_DAYS),
        "iat": datetime.now(timezone.utc),
    }
    return jwt.encode(payload, config.JWT_SECRET, algorithm="HS256")


def verify_token(token):
    """验证 JWT token，成功返回 payload，失败返回 None"""
    try:
        payload = jwt.decode(token, config.JWT_SECRET, algorithms=["HS256"])
        return payload
    except (jwt.ExpiredSignatureError, jwt.InvalidTokenError):
        return None


# ===== 装饰器 =====

def require_auth(f):
    """Flask 路由装饰器：从 Authorization header 提取并验证 JWT。
    验证成功时，在 kwargs 中注入 payload（含 user_id, username）。
    """
    @functools.wraps(f)
    def decorated(*args, **kwargs):
        from flask import request, jsonify

        auth_header = request.headers.get("Authorization", "")
        if not auth_header.startswith("Bearer "):
            return jsonify({"error": "缺少认证令牌"}), 401

        token = auth_header[7:]  # 去掉 "Bearer "
        payload = verify_token(token)
        if payload is None:
            return jsonify({"error": "认证令牌无效或已过期"}), 401

        kwargs["user_payload"] = payload
        return f(*args, **kwargs)

    return decorated

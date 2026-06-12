# -*- coding: utf-8 -*-
"""Flask 主应用 —— 腾讯云 SCF Web 函数模式（端口 9000）"""

import json
import re
import socket
import urllib.request
import urllib.error
from flask import Flask, request, jsonify
from flask_cors import CORS

from server import config
from server import db
from server import auth

app = Flask(__name__)
CORS(app, origins=config.CORS_ORIGINS, supports_credentials=True)


@app.errorhandler(500)
def handle_500(e):
    """统一处理 500 错误，避免泄露数据库连接信息"""
    import pymysql
    if isinstance(e.original_exception, pymysql.err.OperationalError):
        return jsonify({"error": "数据库连接失败，请确认数据库服务已启动"}), 500
    return jsonify({"error": "服务器内部错误"}), 500


# ===== 健康检查 =====

@app.route("/api/health")
def health():
    """健康检查，可选检查数据库连接"""
    result = {
        "status": "ok",
        "service": "yijing-divine",
        "version": config.BUILD_VERSION,
    }
    
    # 尝试连接数据库
    try:
        db._ensure_database()
        conn = db.get_connection()
        with conn.cursor() as cursor:
            cursor.execute("SELECT 1")
            cursor.fetchone()
        conn.close()
        result["db"] = "connected"
    except Exception as e:
        result["db"] = "error"
        result["db_error"] = str(e)
        result["status"] = "degraded"
    
    return jsonify(result)


@app.route("/api/network/deepseek")
def deepseek_network_check():
    """Check whether SCF can reach DeepSeek over public network."""
    url = config.DEEPSEEK_BASE_URL.rstrip("/") + "/"
    req = urllib.request.Request(url, method="GET")
    try:
        with urllib.request.urlopen(req, timeout=5) as resp:
            return jsonify({
                "status": "ok",
                "target": config.DEEPSEEK_BASE_URL,
                "http_status": resp.status,
            })
    except urllib.error.HTTPError as e:
        return jsonify({
            "status": "ok",
            "target": config.DEEPSEEK_BASE_URL,
            "http_status": e.code,
        })
    except (socket.timeout, TimeoutError) as e:
        return jsonify({
            "status": "error",
            "target": config.DEEPSEEK_BASE_URL,
            "error": "timeout",
            "detail": str(e),
        }), 504
    except urllib.error.URLError as e:
        return jsonify({
            "status": "error",
            "target": config.DEEPSEEK_BASE_URL,
            "error": "url_error",
            "detail": str(e.reason),
        }), 502


# ===== 注册 =====

@app.route("/api/auth/register", methods=["POST"])
def register():
    data = request.get_json(force=True)
    username = (data.get("username") or "").strip()
    password = data.get("password") or ""

    if not username or not password:
        return jsonify({"error": "用户名和密码不能为空"}), 400
    if len(username) < 2 or len(username) > 50:
        return jsonify({"error": "用户名长度应为 2-50 字符"}), 400
    if len(password) < 6:
        return jsonify({"error": "密码长度至少 6 位"}), 400

    existing = db.get_user_by_username(username)
    if existing:
        return jsonify({"error": "用户名已存在"}), 409

    password_hash = auth.hash_password(password)
    user_id = db.create_user(username, password_hash)
    token = auth.create_token(user_id, username)

    return jsonify({
        "token": token,
        "user": {"id": user_id, "username": username},
    }), 201


# ===== 登录 =====

@app.route("/api/auth/login", methods=["POST"])
def login():
    data = request.get_json(force=True)
    username = (data.get("username") or "").strip()
    password = data.get("password") or ""

    user = db.get_user_by_username(username)
    if not user or not auth.verify_password(password, user["password_hash"]):
        return jsonify({"error": "用户名或密码错误"}), 401

    token = auth.create_token(user["id"], user["username"])
    return jsonify({
        "token": token,
        "user": {"id": user["id"], "username": user["username"]},
    })


# ===== 用户信息 =====

@app.route("/api/user/info")
@auth.require_auth
def user_info(user_payload):
    user_id = user_payload["user_id"]
    today_count = db.get_daily_count(user_id)
    remaining = config.DAILY_AI_LIMIT - today_count

    return jsonify({
        "user": {
            "id": user_id,
            "username": user_payload["username"],
        },
        "daily_limit": config.DAILY_AI_LIMIT,
        "today_used": today_count,
        "remaining": max(remaining, 0),
    })


# ===== 起卦 + AI 解读 =====

@app.route("/api/divine", methods=["POST"])
@auth.require_auth
def divine(user_payload):
    user_id = user_payload["user_id"]
    data = request.get_json(force=True)
    question = data.get("question", "")
    hexagram_data = data.get("hexagram_data", {})

    if not question:
        return jsonify({"error": "请输入您的问题"}), 400

    # 检查今日额度
    today_count = db.get_daily_count(user_id)
    if today_count >= config.DAILY_AI_LIMIT:
        remaining = max(config.DAILY_AI_LIMIT - today_count, 0)
        return jsonify({
            "error": f"今日 AI 解读次数已用完（每日 {config.DAILY_AI_LIMIT} 次），请明天再试。",
            "remaining": remaining,
        }), 403

    # 构建 prompt
    sys_prompt, user_prompt = _build_prompts(question, hexagram_data)

    # 调用 DeepSeek API
    try:
        ai_response = _call_deepseek(sys_prompt, user_prompt)
        ai_response = _normalize_ai_response(ai_response)
    except TimeoutError as e:
        return jsonify({"error": f"AI 服务响应超时：{str(e)}"}), 504
    except Exception as e:
        return jsonify({"error": f"AI 服务调用失败：{str(e)}"}), 502

    # 保存记录
    try:
        record_id, used_count = db.save_divination_and_increment_usage(
            user_id, question, hexagram_data, ai_response
        )
    except Exception as e:
        return jsonify({"error": "起卦记录保存失败：" + str(e)}), 500

    remaining = config.DAILY_AI_LIMIT - used_count

    return jsonify({
        "ai_response": ai_response,
        "record_id": record_id,
        "remaining": max(remaining, 0),
    })


# ===== 历史记录 =====

@app.route("/api/history")
@auth.require_auth
def history(user_payload):
    user_id = user_payload["user_id"]
    page = request.args.get("page", 1, type=int)
    page_size = request.args.get("page_size", 20, type=int)
    page_size = min(page_size, 50)

    records, total = db.get_history(user_id, page, page_size)
    return jsonify({
        "records": records,
        "total": total,
        "page": page,
        "page_size": page_size,
    })


# ===== 单条详情 =====

@app.route("/api/history/<int:div_id>")
@auth.require_auth
def history_detail(user_payload, div_id):
    user_id = user_payload["user_id"]
    record = db.get_divination(div_id, user_id)
    if not record:
        return jsonify({"error": "记录不存在"}), 404
    return jsonify(record)


# ===== Prompt 构建（复用前端逻辑）=====

def _build_prompts(question, hd):
    """根据前端传来的卦象数据构建 system prompt 和 user prompt"""
    # 提取字段，兼容不同命名
    gz = hd.get("ganzhi", {})
    solar = hd.get("solar", {})
    ben = hd.get("benGua", {})
    bian = hd.get("bianGua", {})

    # 四柱
    year_gz = gz.get("year", {})
    month_gz = gz.get("month", {})
    day_gz = gz.get("day", {})
    hour_gz = gz.get("hour", {})

    # 动爻
    my = hd.get("movingYao", 1)

    # 动爻爻辞
    yaoci_list = ben.get("yaoci", [])
    moving_yao = yaoci_list[my - 1] if yaoci_list and my >= 1 else {}
    moving_text = moving_yao.get("text", "")
    moving_trans = moving_yao.get("translation", "")

    # 天干五行（尝试从 hexagram_data 提取，或用空值）
    tiangan_list = hd.get("tiangan", [])
    dizhi_list = hd.get("dizhi", [])
    day_gan_idx = day_gz.get("ganIdx", 0)
    hour_zhi_idx = hour_gz.get("zhiIdx", 0)

    # 从嵌入的 bagua 数据中获取天干地支五行
    # 前端会传 tiangan 和 dizhi 数组，或者我们硬编码
    day_gan_wuxing = _get_tiangan_wuxing(day_gz.get("gan", ""))
    hour_zhi_wuxing = _get_dizhi_wuxing(hour_gz.get("zhi", ""))

    sys_prompt = f"""你是一位精通周易和梅花易数的大师。用户通过时间起卦得到卦象，请综合分析并回答用户的问题。

要求：
1. 严格按以下顺序输出四段：决策摘要、卦象依据、动爻变化、时势补充
2. 每段标题使用“决策摘要：”这种中文标题加冒号的形式，不要使用 Markdown 标记，不要输出 #、###、**、-、1. 等格式符号
3. “决策摘要”必须放在最前面，并且只包含四行：当前态势：、关键阻力：、建议动作：、留意项：
4. “留意项”只写一个温和提醒，不要把风险提示写成与前三项平级的结论
5. “卦象依据”概括本卦的整体含义和启示，并说明它如何对应用户的问题
6. “动爻变化”分析动爻的关键信息（原文及译文：{moving_text}——{moving_trans}），并说明变卦方向
7. “时势补充”结合四柱干支（日主{day_gz.get('gan','')}{day_gz.get('zhi','')}属{day_gan_wuxing}，时支{hour_gz.get('zhi','')}属{hour_zhi_wuxing}）分析五行旺衰对卦象的影响
8. 不要编造卦辞爻辞，经文引用必须与原文一致
9. 320-520字，短句优先，语言流畅自然，保持学术格调但不晦涩"""

    # 上下卦信息
    upper_num = hd.get("upper", 1)
    lower_num = hd.get("lower", 8)
    upper_name = ben.get("upper_name", "")
    upper_nature = ben.get("upper_nature", "")
    upper_wuxing = ben.get("upper_wuxing", "")
    lower_name = ben.get("lower_name", "")
    lower_nature = ben.get("lower_nature", "")
    lower_wuxing = ben.get("lower_wuxing", "")
    minute = solar.get("minute", "")
    minute_text = f"{minute}分" if minute not in (None, "") else ""

    user_prompt = f"""用户的问题：{question}

起卦时间：{solar.get('year','')}年{solar.get('month','')}月{solar.get('day','')}日{solar.get('hour','')}时{minute_text}
四柱：{year_gz.get('gan','')}{year_gz.get('zhi','')}年 {month_gz.get('gan','')}{month_gz.get('zhi','')}月 {day_gz.get('gan','')}{day_gz.get('zhi','')}日 {hour_gz.get('gan','')}{hour_gz.get('zhi','')}时
日主五行：{day_gan_wuxing}  时支五行：{hour_zhi_wuxing}

本卦：第{ben.get('id','')}卦 {ben.get('full_name','')}（{ben.get('jijing','')}）
上卦：{upper_name}（{upper_nature}，五行{upper_wuxing}）
下卦：{lower_name}（{lower_nature}，五行{lower_wuxing}）
卦辞：{ben.get('gua_ci','')}
卦辞译文：{ben.get('gua_ci_translation','无')}
大象：{ben.get('xiang_ci','')}
大象译文：{ben.get('xiang_ci_translation','无')}

动爻：第{my}爻（{moving_yao.get('type','')}{_pos_name(my)}）
动爻爻辞：{moving_text}
动爻译文：{moving_trans}

变卦：第{bian.get('id','')}卦 {bian.get('full_name','')}
变卦卦辞：{bian.get('gua_ci','')}
变卦译文：{bian.get('gua_ci_translation','无')}

请综合以上信息，针对用户的问题给出解读。"""

    return sys_prompt, user_prompt


def _normalize_ai_response(text):
    """Remove common Markdown markers so old frontends still display clean text."""
    if not text:
        return ""

    text = text.replace("\r\n", "\n").replace("\r", "\n")
    lines = []
    for raw in text.split("\n"):
        line = raw.strip()
        if not line:
            lines.append("")
            continue

        heading = re.match(r"^#{1,6}\s*(.+?)\s*$", line)
        if heading:
            title = heading.group(1).strip(" :")
            if title:
                line = title + ":"

        line = re.sub(r"\*\*(.*?)\*\*", r"\1", line)
        line = re.sub(r"__(.*?)__", r"\1", line)
        line = re.sub(r"^\s*[-*+]\s+", "", line)
        line = re.sub(r"^\s*\d+[.)]\s+", "", line)
        lines.append(line)

    cleaned = "\n".join(lines)
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned).strip()
    return cleaned


def _call_deepseek(sys_prompt, user_prompt):
    """调用 DeepSeek API（使用 stdlib urllib，无外部依赖）"""
    url = config.DEEPSEEK_BASE_URL.rstrip("/") + "/chat/completions"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {config.DEEPSEEK_API_KEY}",
    }
    payload = {
        "model": config.DEEPSEEK_MODEL,
        "messages": [
            {"role": "system", "content": sys_prompt},
            {"role": "user", "content": user_prompt},
        ],
        "temperature": 0.7,
        "max_tokens": 700,
        "thinking": {"type": "disabled"},
    }
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=45) as resp:
            resp_data = json.loads(resp.read().decode("utf-8"))
            content = resp_data["choices"][0]["message"]["content"]
            return content
    except (socket.timeout, TimeoutError):
        raise TimeoutError("DeepSeek API 响应超时，请稍后重试")
    except urllib.error.HTTPError as e:
        error_body = e.read().decode("utf-8")
        raise Exception(f"DeepSeek API 错误 {e.code}: {error_body}")
    except urllib.error.URLError as e:
        if isinstance(e.reason, (socket.timeout, TimeoutError)) or str(e.reason).lower() == "timed out":
            raise TimeoutError("DeepSeek API 连接超时，请检查 SCF 公网出口")
        raise Exception(f"DeepSeek API 连接失败: {e.reason}")


# ===== 天干地支五行（硬编码，与前端一致）=====

_TG_WX = {
    "甲": "木", "乙": "木", "丙": "火", "丁": "火",
    "戊": "土", "己": "土", "庚": "金", "辛": "金",
    "壬": "水", "癸": "水",
}

_DZ_WX = {
    "子": "水", "丑": "土", "寅": "木", "卯": "木",
    "辰": "土", "巳": "火", "午": "火", "未": "土",
    "申": "金", "酉": "金", "戌": "土", "亥": "水",
}

_BG_NAMES = {1: "乾", 2: "兑", 3: "离", 4: "震", 5: "巽", 6: "坎", 7: "艮", 8: "坤"}
_BG_NATURE = {1: "天", 2: "泽", 3: "火", 4: "雷", 5: "风", 6: "水", 7: "山", 8: "地"}
_BG_WX = {1: "金", 2: "金", 3: "火", 4: "木", 5: "木", 6: "水", 7: "土", 8: "土"}


def _get_tiangan_wuxing(gan):
    return _TG_WX.get(gan, "未知")


def _get_dizhi_wuxing(zhi):
    return _DZ_WX.get(zhi, "未知")


def _pos_name(p):
    return ["", "初", "二", "三", "四", "五", "上"][p] if 0 < p < 7 else str(p)


# ===== SCF 入口 =====

if __name__ == "__main__":
    # 本地开发模式
    db.init_db()
    app.run(host="0.0.0.0", port=9000, debug=True)

# -*- coding: utf-8 -*-
"""SCF Web 函数入口 —— Flask 启动脚本"""

import sys
import os

# 依赖在代码包根目录（被打包进 zip）
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from server.app import app
from server import db

if __name__ == "__main__":
    try:
        db.init_db()
    except Exception as e:
        print("[WARN] 数据库初始化失败（可能未配置 VPC）: %s" % e)
    app.run(host="0.0.0.0", port=9000, debug=False)

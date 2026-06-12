# -*- coding: utf-8 -*-
"""
重建 SCF 部署包（SCF Python 3.9 兼容）
使用旧版依赖，避免 X|Y 类型语法、contextvars、from __future__ import annotations 等问题
"""
import zipfile, os, shutil, subprocess, sys

PROJECT_DIR = r"C:\Users\lky\WorkBuddy\Claw"
BUILD_DIR = os.path.join(PROJECT_DIR, "scf_build_v2")
ZIP_PATH = os.path.join(PROJECT_DIR, "scf_deploy.zip")

PYTHON = r"C:\Users\lky\.workbuddy\binaries\python\versions\3.13.12\python.exe"

# 严格兼容 Python 3.7 的依赖版本（无 X|Y 语法，无 contextvars）
REQUIREMENTS = [
    "flask==2.0.3",
    "werkzeug==2.0.3",
    "jinja2==3.0.3",
    "markupsafe==2.0.1",
    "itsdangerous==2.0.1",
    "click==8.0.4",
    "flask-cors==3.0.10",
    "PyJWT==2.3.0",
    "pymysql==1.0.3",
    "certifi==2021.10.8",
    "colorama==0.4.4",
]

def main():
    if os.path.exists(BUILD_DIR):
        shutil.rmtree(BUILD_DIR)
    os.makedirs(BUILD_DIR, exist_ok=True)

    venv_dir = os.path.join(BUILD_DIR, "_venv")
    print(f"创建虚拟环境...")
    subprocess.run([PYTHON, "-m", "venv", venv_dir], check=True, capture_output=True)
    pip = os.path.join(venv_dir, "Scripts", "pip.exe") if sys.platform == "win32" else os.path.join(venv_dir, "bin", "pip")

    print("安装依赖（Python 3.7 兼容版本）...")
    subprocess.run([pip, "install", "--no-cache-dir", "--target", BUILD_DIR] + REQUIREMENTS, check=True)

    # 补丁：移除 from __future__ import annotations（SCF 不支持）
    print("打补丁：移除 from __future__ import annotations ...")
    removed = 0
    for root, dirs, files in os.walk(BUILD_DIR):
        for fname in files:
            if not fname.endswith(".py"):
                continue
            fpath = os.path.join(root, fname)
            try:
                with open(fpath, "r", encoding="utf-8") as f:
                    lines = f.readlines()
                new_lines = [l for l in lines if "from __future__ import annotations" not in l]
                if len(new_lines) < len(lines):
                    with open(fpath, "w", encoding="utf-8") as f:
                        f.writelines(new_lines)
                    removed += 1
            except Exception:
                pass
    print(f"  已处理 {removed} 个文件")

    # 复制项目代码
    print("复制项目代码...")
    server_dst = os.path.join(BUILD_DIR, "server")
    server_src = os.path.join(PROJECT_DIR, "server")
    shutil.copytree(server_src, server_dst, ignore=shutil.ignore_patterns("__pycache__", ".venv", "*.pyc"))
    init_file = os.path.join(server_dst, "__init__.py")
    if not os.path.exists(init_file):
        with open(init_file, "w") as f:
            f.write("")

    shutil.copy2(os.path.join(PROJECT_DIR, "scf_handler.py"), BUILD_DIR)

    bootstrap_src = os.path.join(PROJECT_DIR, "scf_bootstrap")
    bootstrap_dst = os.path.join(BUILD_DIR, "scf_bootstrap")
    with open(bootstrap_src, "r", encoding="utf-8") as f:
        content = f.read()
    with open(bootstrap_dst, "w", newline="\n") as f:
        f.write(content)

    # 删除旧 zip
    if os.path.exists(ZIP_PATH):
        os.remove(ZIP_PATH)

    # 创建 zip
    print("创建部署包...")
    with zipfile.ZipFile(ZIP_PATH, "w", zipfile.ZIP_DEFLATED) as zf:
        for root, dirs, files in os.walk(BUILD_DIR):
            dirs[:] = [d for d in dirs if d not in ("__pycache__", "_venv", ".venv")]
            for file in files:
                if file.endswith(".pyc"):
                    continue
                file_path = os.path.join(root, file)
                arcname = os.path.relpath(file_path, BUILD_DIR)
                zf.write(file_path, arcname)

    size_mb = os.path.getsize(ZIP_PATH) / 1024 / 1024
    print(f"\n部署包: {ZIP_PATH} ({size_mb:.2f} MB)")
    print("构建完成！")

if __name__ == "__main__":
    main()

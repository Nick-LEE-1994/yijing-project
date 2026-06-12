# -*- coding: utf-8 -*-
"""重建 SCF 部署包（Python 3.9 兼容版本）"""
import zipfile
import os
import shutil
import subprocess
import sys

PROJECT_DIR = r"C:\Users\lky\WorkBuddy\Claw"
BUILD_DIR = os.path.join(PROJECT_DIR, "scf_build_v2")
ZIP_PATH = os.path.join(PROJECT_DIR, "scf_deploy.zip")

PYTHON = r"C:\Users\lky\.workbuddy\binaries\python\versions\3.13.12\python.exe"

# 依赖（恢复 Flask 3.x，提供 contextvars 兼容实现）
REQUIREMENTS = [
    "flask==3.0.3",
    "flask-cors==4.0.1",
    "PyJWT==2.8.0",
    "pymysql==1.1.0",
    "werkzeug==3.0.3",
    "jinja2==3.1.3",
    "markupsafe==2.1.5",
    "itsdangerous==2.1.2",
    "click==8.1.7",
    "blinker==1.7.0",
    "colorama",
    "certifi==2023.11.17",
]

def main():
    # 清理构建目录
    if os.path.exists(BUILD_DIR):
        shutil.rmtree(BUILD_DIR)
    os.makedirs(BUILD_DIR, exist_ok=True)

    # 创建虚拟环境用于安装依赖
    venv_dir = os.path.join(BUILD_DIR, "_venv")
    print(f"创建虚拟环境: {venv_dir}")
    subprocess.run([PYTHON, "-m", "venv", venv_dir], check=True, capture_output=True)

    pip = os.path.join(venv_dir, "Scripts", "pip.exe") if sys.platform == "win32" else os.path.join(venv_dir, "bin", "pip")
    site_packages = os.path.join(venv_dir, "Lib", "site-packages") if sys.platform == "win32" else os.path.join(venv_dir, "lib", f"python{sys.version_info.major}.{sys.version_info.minor}", "site-packages")

    # 安装依赖到构建根目录
    print("安装依赖...")
    subprocess.run([pip, "install", "--no-cache-dir", "--target", BUILD_DIR] + REQUIREMENTS, check=True)

    # 补丁：移除所有 .py 文件中的 from __future__ import annotations
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

    # 复制 server/ 目录
    server_dst = os.path.join(BUILD_DIR, "server")
    server_src = os.path.join(PROJECT_DIR, "server")
    shutil.copytree(server_src, server_dst, ignore=shutil.ignore_patterns("__pycache__", ".venv", "*.pyc"))

    # 确保 server/__init__.py 存在
    init_file = os.path.join(server_dst, "__init__.py")
    if not os.path.exists(init_file):
        with open(init_file, "w") as f:
            f.write("")

    # 复制 scf_handler.py
    shutil.copy2(os.path.join(PROJECT_DIR, "scf_handler.py"), BUILD_DIR)

    # 复制 scf_bootstrap
    bootstrap_src = os.path.join(PROJECT_DIR, "scf_bootstrap")
    bootstrap_dst = os.path.join(BUILD_DIR, "scf_bootstrap")
    with open(bootstrap_src, "r", encoding="utf-8") as f:
        content = f.read()
    # Linux SCF 的 python3 路径
    content = content.replace("/var/lang/python3/bin/python3", "/var/lang/python3/bin/python3")
    with open(bootstrap_dst, "w", newline="\n") as f:
        f.write(content)

    # 复制 contextvars.py（SCF Python 3.9 标准库缺少此模块，提供兼容实现）
    print("复制 contextvars.py ...")
    shutil.copy2(os.path.join(PROJECT_DIR, "contextvars.py"), os.path.join(BUILD_DIR, "contextvars.py"))

    # 删除旧的 zip
    if os.path.exists(ZIP_PATH):
        os.remove(ZIP_PATH)

    # 创建 zip
    print("创建部署包...")
    with zipfile.ZipFile(ZIP_PATH, "w", zipfile.ZIP_DEFLATED) as zf:
        for root, dirs, files in os.walk(BUILD_DIR):
            # 跳过 __pycache__ 和 _venv
            dirs[:] = [d for d in dirs if d not in ("__pycache__", "_venv", ".venv")]
            for file in files:
                if file.endswith(".pyc"):
                    continue
                file_path = os.path.join(root, file)
                arcname = os.path.relpath(file_path, BUILD_DIR)
                zf.write(file_path, arcname)

    size_mb = os.path.getsize(ZIP_PATH) / 1024 / 1024
    print(f"\n部署包已创建: {ZIP_PATH}")
    print(f"大小: {size_mb:.2f} MB")

    # 列出 zip 内容
    print("\nzip 内容预览:")
    with zipfile.ZipFile(ZIP_PATH, "r") as zf:
        names = zf.namelist()
        print(f"总文件数: {len(names)}")
        for name in sorted(names)[:20]:
            info = zf.getinfo(name)
            print(f"  {name} ({info.file_size} bytes)")
        if len(names) > 20:
            print(f"  ... 还有 {len(names) - 20} 个文件")

if __name__ == "__main__":
    main()

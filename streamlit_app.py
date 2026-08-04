# -*- coding: utf-8 -*-
"""
Travel Agent 启动器

使用方式：
    python streamlit_app.py

本脚本会自动启动 Streamlit 服务器，
主应用文件为 src/agent/frontend/main_app.py，
Streamlit 会自动识别同级 pages/ 目录下的多页面。
"""

import sys
import os
import subprocess

# 项目根目录
PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
MAIN_APP = os.path.join("travel_agent", "frontend", "main_app.py")

print(f"🚀 正在启动 Travel Agent...")
print(f"   主应用: {MAIN_APP}")
print(f"   访问地址: http://localhost:8501")
print()

# 启动 Streamlit 子进程（阻塞运行）
result = subprocess.run(
    [sys.executable, "-m", "streamlit", "run", MAIN_APP],
    cwd=PROJECT_ROOT,
    env={**os.environ, "PYTHONPATH": PROJECT_ROOT},
)

sys.exit(result.returncode)
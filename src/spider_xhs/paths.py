"""集中管理项目关键路径，避免各模块用 `../..` 硬拼路径。

目录布局（仓库根）:
    src/spider_xhs/   源码包
    assets/js/        JS 签名脚本（execjs 运行时加载）
    datas/            采集产物（媒体 / excel）
    config/           配置样例
"""
import os
from pathlib import Path

PACKAGE_DIR = Path(__file__).resolve().parent          # src/spider_xhs
SRC_DIR = PACKAGE_DIR.parent                            # src
REPO_ROOT = SRC_DIR.parent                             # 仓库根

# JS 签名脚本目录（可用环境变量覆盖，便于容器/自定义部署）
ASSETS_JS_DIR = Path(os.getenv("XHS_ASSETS_JS_DIR", "").strip() or (REPO_ROOT / "assets" / "js"))

# 采集产物默认根目录
DATAS_DIR = REPO_ROOT / "datas"


def static_js_dir() -> str:
    """返回 JS 资源目录（字符串），供 execjs 读取脚本使用。"""
    return str(ASSETS_JS_DIR)

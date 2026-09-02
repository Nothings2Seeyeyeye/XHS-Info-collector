"""项目入口 shim。

保持 `python main.py` / `uv run main.py` 的既有用法不变：
- 将 ``src`` 加入模块搜索路径，无需额外安装即可导入 ``spider_xhs`` 包；
- 必须在项目根目录运行，确保 JS 签名依赖的 ``node_modules`` 与 ``.env`` 可被解析。
"""
import os
import sys

_SRC_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "src")
if _SRC_DIR not in sys.path:
    sys.path.insert(0, _SRC_DIR)

from spider_xhs.cli import main

if __name__ == "__main__":
    main()

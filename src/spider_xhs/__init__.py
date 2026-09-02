"""Spider_XHS 核心包。

分层约定：
- ``spider_xhs.cli``    入口编排（命令行/交互菜单）
- ``spider_xhs.apis``   小红书接口适配层
- ``spider_xhs.utils``  签名、请求、数据处理等基础能力
- ``spider_xhs.paths``  统一的路径解析（仓库根、资源目录、数据目录）
"""

__all__ = ["paths"]

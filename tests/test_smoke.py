"""基础冒烟测试：验证重构后包结构、资源路径与 JS 签名桥接完好。

这些用例不依赖网络或 Cookie，可离线运行：
    uv run python -m pytest tests            # 或
    .venv/bin/python -m pytest tests
"""
import os


def test_paths_resolve_repo_root():
    from spider_xhs import paths

    assert paths.REPO_ROOT.name == "02-个人魔改" or paths.REPO_ROOT.is_dir()
    assert (paths.REPO_ROOT / "assets" / "js").is_dir()
    assert os.path.isfile(os.path.join(paths.static_js_dir(), "xhs_main_260411.js"))


def test_imports_cli():
    from spider_xhs.cli import main  # noqa: F401


def test_signing_bridge_works():
    """execjs + node_modules + assets/js 三者链路是否可用（签名产物非空）。"""
    from spider_xhs.utils.xhs_util import generate_xs_xs_common

    xs, xt, xs_common = generate_xs_xs_common("a1test", "/api/sns/web/v1/feed", "")
    assert xs and str(xt) and xs_common

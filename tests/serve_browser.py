"""Disposable browser-test server. Never operates on the real user's library."""
import os
import subprocess
import sys
import tempfile
from pathlib import Path

root = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(root / "src"), str(root)]
temporary = Path(tempfile.mkdtemp(prefix="xhs-browser-test-"))
os.environ.update({"XHS_APP_DATA": str(temporary / "app"), "XHS_MEDIA_BASE": str(temporary / "media"),
                   "XHS_EXCEL_BASE": str(temporary / "excel"), "COOKIES": "", "OCR_TOKEN": "",
                   "PYTHONPATH": str(root / "src")})
from tests.test_web import make_note
from spider_xhs.web.app import create_app
from spider_xhs.web.db import Store
from spider_xhs.utils.data_util import save_ai_context
import uvicorn

first, path = make_note(temporary / "media")
second, other_path = make_note(temporary / "media", "b" * 24, "旅行摄影备忘")
from PIL import Image
Image.new("RGB", (60, 80), "#c79f76").save(path / "image_1.jpg")
Image.new("RGB", (60, 80), "#c79f76").save(path / "png/image_1.png")
first["image_list"].append("https://example.invalid/image2.jpg")
import json
(path / "info.json").write_text(json.dumps(first, ensure_ascii=False), encoding="utf-8")
(path / "ocr").mkdir()
(path / "ocr/image_0.md").write_text("这是一段已经识别的独特露营清单文字", encoding="utf-8")
save_ai_context(first, str(path))
store = Store()
worker = subprocess.Popen([sys.executable, "-m", "spider_xhs.web.worker"])
try:
    uvicorn.run(create_app(store), host="127.0.0.1", port=8877, access_log=False)
finally:
    worker.terminate()
    worker.wait(timeout=20)

"""One entry point for the localhost server and its durable worker."""
import argparse
import os
import socket
import subprocess
import sys
import threading
import time
import urllib.request
import webbrowser

import uvicorn
from spider_xhs.paths import REPO_ROOT
from .app import create_app
from .db import Store


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--no-browser", action="store_true")
    parser.add_argument("--no-worker", action="store_true", help="仅用于开发和离线测试")
    args = parser.parse_args()
    os.chdir(REPO_ROOT)
    with socket.socket() as probe:
        if probe.connect_ex(("127.0.0.1", args.port)) == 0:
            raise SystemExit(f"端口 {args.port} 已被占用，请关闭已运行的实例或指定其他端口")
    store = Store()
    app = create_app(store)
    worker = None
    if not args.no_worker:
        worker = subprocess.Popen([sys.executable, "-m", "spider_xhs.web.worker"])
    url = f"http://127.0.0.1:{args.port}"

    def open_when_ready():
        for _ in range(80):
            try:
                with urllib.request.urlopen(url + "/api/auth/status", timeout=1):
                    webbrowser.open(url)
                    return
            except Exception:
                time.sleep(0.25)

    if not args.no_browser:
        threading.Thread(target=open_when_ready, daemon=True).start()
    print(f"拾页已启动：{url}\n关闭网页后任务继续运行；按 Ctrl+C 停止服务，下次启动自动恢复任务。", flush=True)
    try:
        uvicorn.run(app, host="127.0.0.1", port=args.port, access_log=False)
    finally:
        if worker:
            worker.terminate()
            try:
                worker.wait(timeout=30)
            except subprocess.TimeoutExpired:
                worker.kill()
                worker.wait()
        store.close()


if __name__ == "__main__":
    main()

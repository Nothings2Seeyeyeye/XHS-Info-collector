"""Offline integration coverage for local data, permissions and resumable jobs."""
import io
import json
import time
import zipfile
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from PIL import Image
from sqlalchemy import select

from spider_xhs.web.app import create_app
from spider_xhs.web.db import Folder, Job, JobItem, Note, NoteFolder, NoteTag, Store
from spider_xhs.web.library import import_existing
from spider_xhs.web.tasks import DurableOCR, LoginRequired, PlatformBlocked, Runner, TaskStopped, WebXHS, checked, parse_sources
from spider_xhs.web.worker import recover


def make_note(media, note_id="a" * 24, title="露营收纳灵感", kind="图集"):
    data = dict(note_id=note_id, note_url=f"https://www.xiaohongshu.com/explore/{note_id}?xsec_token=test",
                note_type=kind, user_id="author1", home_url="https://www.xiaohongshu.com/user/profile/author1",
                nickname="测试作者", avatar="", title=title, desc="周末露营，轻装出发。", liked_count="12", collected_count="3",
                comment_count="1", share_count="0", video_cover=None, video_addr=None, image_list=["https://example.invalid/image.jpg"],
                tags=["露营", "收纳"], upload_time="2026-09-02 10:00:00", ip_location="上海")
    base = media / "测试作者_author1" / f"{title}_{note_id}"
    base.mkdir(parents=True)
    (base / "info.json").write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    Image.new("RGB", (60, 80), "#719579").save(base / "image_0.jpg")
    (base / "png").mkdir()
    Image.new("RGB", (60, 80), "#719579").save(base / "png/image_0.png")
    from spider_xhs.utils.data_util import save_ai_context, save_note_detail
    save_note_detail(data, str(base))
    save_ai_context(data, str(base))
    return data, base


@pytest.fixture
def env(tmp_path):
    media = tmp_path / "media"
    data, path = make_note(media)
    store = Store(tmp_path / "app", media)
    store.excel = tmp_path / "excel"
    store.excel.mkdir()
    with TestClient(create_app(store)) as client:
        yield store, client, data, path
    store.close()


def login(client):
    result = client.post("/api/auth/setup", json={"username": "tester", "password": "test-password-123"})
    assert result.status_code == 200, result.text


def test_bootstrap_sessions_origin_and_secrets(env):
    store, client, data, path = env
    assert client.get("/api/notes").status_code == 401
    assert client.get(f"/api/media/{data['note_id']}/info.json").status_code == 401
    assert client.get("/api/auth/status").json()["initialized"] is False
    assert client.post("/api/auth/setup", headers={"Origin": "https://untrusted.invalid"}, json={"username": "a", "password": "12345678"}).status_code == 403
    login(client)
    assert client.post("/api/auth/setup", json={"username": "other", "password": "12345678"}).status_code == 409
    assert client.get("/api/auth/status").json()["username"] == "tester"
    store.put_secret("ocr_key", "a-test-key-only")
    assert store.get("ocr_key") != "a-test-key-only"
    settings = client.get("/api/settings/ocr").json()
    assert settings["has_key"] and "key" not in settings
    assert "httponly" in client.cookies.jar._cookies["testserver.local"]["/"]["xhs_library_session"]._rest.keys() or client.cookies.get("xhs_library_session")
    client.post("/api/auth/logout")
    assert client.get("/api/overview").status_code == 401
    assert client.post("/api/auth/login", json={"username": "tester", "password": "wrong-password"}).status_code == 401
    assert client.post("/api/auth/login", json={"username": "tester", "password": "test-password-123"}).status_code == 200


def test_import_search_preview_and_safe_files(env):
    store, client, data, path = env
    login(client)
    assert import_existing(store)["imported"] == 0
    listing = client.get("/api/notes", params={"q": "露营"}).json()
    assert listing["total"] == 1
    item = listing["items"][0]
    assert item["cover"].endswith("image_0.jpg")
    assert client.get(item["cover"]).headers["content-type"] == "image/jpeg"
    video = path / "video_files/video.mp4"
    video.parent.mkdir()
    video.write_bytes(bytes(range(256)) * 10)
    chunk = client.get(f"/api/media/{data['note_id']}/video_files/video.mp4", headers={"Range": "bytes=100-199"})
    assert chunk.status_code == 206
    assert len(chunk.content) == 100
    assert chunk.headers["content-range"] == "bytes 100-199/2560"
    assert client.get("/api/notes", params={"original_tag": "露"}).json()["total"] == 0
    assert client.get("/api/notes", params={"original_tag": "露营"}).json()["total"] == 1
    assert client.get("/api/notes", params={"q": "%"}).json()["total"] == 0
    assert client.get(f"/api/media/{data['note_id']}/..%2F..%2F..%2Fapp%2Fsecret.key").status_code == 404
    (path / "escape.txt").symlink_to(store.root / "secret.key")
    assert client.get(f"/api/media/{data['note_id']}/escape.txt").status_code == 404
    detail = client.get(f"/api/notes/{data['note_id']}").json()
    assert "note_ai_context.txt" in str(detail["files"])


def test_folders_multiple_membership_cycles_tags_and_trash(env):
    store, client, data, path = env
    login(client)
    first = client.post("/api/folders", json={"name": "选题"}).json()["id"]
    second = client.post("/api/folders", json={"name": "拍摄", "parent_id": first}).json()["id"]
    assert client.patch(f"/api/folders/{first}", json={"name": "选题", "parent_id": second}).status_code == 422
    for folder in [first, second]:
        assert client.post("/api/organize", json={"action": "add_folder", "value": folder, "note_ids": [data["note_id"]]}).status_code == 200
    assert len(client.get(f"/api/notes/{data['note_id']}").json()["folder_ids"]) == 2
    client.post("/api/organize", json={"action": "add_tag", "value": "待拍摄", "note_ids": [data["note_id"]]})
    assert client.get("/api/notes", params={"q": "待拍摄"}).json()["total"] == 1
    client.post("/api/organize", json={"action": "trash", "note_ids": [data["note_id"]]})
    assert client.get("/api/notes").json()["total"] == 0
    assert client.get("/api/notes?trash=true").json()["total"] == 1
    assert import_existing(store)["imported"] == 0
    client.post("/api/organize", json={"action": "restore", "note_ids": [data["note_id"]]})
    assert len(client.get(f"/api/notes/{data['note_id']}").json()["folder_ids"]) == 2
    assert client.delete(f"/api/folders/{first}").status_code == 200
    assert client.get("/api/overview").json()["folders"] == []
    assert path.exists() and client.get("/api/notes").json()["total"] == 1


def test_export_preserves_existing_pair_and_purge(env):
    store, client, data, path = env
    login(client)
    response = client.post("/api/exports", json={"note_ids": [data["note_id"]], "format": "context"})
    assert response.status_code == 200, response.text
    archive = zipfile.ZipFile(io.BytesIO(client.get(response.json()["url"]).content))
    assert f"{data['note_id']}/ai_context/note_ai_context.txt" in archive.namelist()
    assert f"{data['note_id']}/ai_context/note_ai_context.json" in archive.namelist()
    assert not any(name.endswith(".jpg") for name in archive.namelist())
    xlsx = client.post("/api/exports", json={"note_ids": [data["note_id"]], "format": "excel"}).json()
    assert client.get(xlsx["url"]).content.startswith(b"PK")
    client.post("/api/organize", json={"action": "trash", "note_ids": [data["note_id"]]})
    with store.session() as db:
        job = Job(title="进行中的任务", state="running")
        db.add(job)
        db.flush()
        job_id = job.id
        db.add(JobItem(job_id=job.id, item_key=data["note_id"], note_id=data["note_id"]))
    assert client.post("/api/trash/purge", json={"note_ids": []}).status_code == 409
    client.post(f"/api/jobs/{job_id}/cancel")
    assert client.post("/api/trash/purge", json={"note_ids": []}).status_code == 200
    assert not path.exists()


def test_restart_recovery_preserves_manual_states(env):
    store, client, data, path = env
    ids = {}
    with store.session() as db:
        for state in ["running", "paused", "cancelled", "completed", "waiting_login"]:
            job = Job(title=state, state=state)
            db.add(job)
            db.flush()
            ids[state] = job.id
            db.add(JobItem(job_id=job.id, item_key="finished", state="done"))
            db.add(JobItem(job_id=job.id, item_key="unfinished", state="running" if state == "running" else "pending"))
    recover(store)
    with store.session() as db:
        for state, job_id in ids.items():
            assert db.get(Job, job_id).state == ("queued" if state == "running" else state)
            assert db.scalar(select(JobItem.state).where(JobItem.job_id == job_id, JobItem.item_key == "finished")) == "done"


def test_existing_note_collect_is_offline_and_keeps_organization(env, monkeypatch):
    store, client, data, path = env
    login(client)
    client.post("/api/organize", json={"action": "add_tag", "value": "个人分类", "note_ids": [data["note_id"]]})
    job_id = client.post("/api/jobs", json={"input": data["note_url"], "mode": "auto"}).json()["id"]
    monkeypatch.setattr("spider_xhs.utils.network.request", lambda *a, **k: pytest.fail("existing note must not request XHS"))
    with store.session() as db:
        db.get(Job, job_id).state = "running"
    Runner(store, job_id).run()
    job = client.get(f"/api/jobs/{job_id}").json()
    assert job["state"] == "completed", job
    assert job["counts"] == {"skipped": 1}
    assert client.get(f"/api/notes/{data['note_id']}").json()["tags"] == ["个人分类"]


def test_auth_failures_pause_only_collection_and_403_is_not_expiry(env):
    store, client, data, path = env
    assert WebXHS()._is_risk_response(401, "", {})[1].startswith("[AUTH_REQUIRED]")
    assert "[AUTH_REQUIRED]" not in WebXHS()._is_risk_response(403, "", {})[1]
    blocked, message = WebXHS()._is_risk_response(461, "", {"code": 300012, "msg": "IP存在风险"})
    assert blocked and "[PLATFORM_BLOCKED]" in message
    with pytest.raises(PlatformBlocked):
        checked((False, message, None))
    assert WebXHS()._is_risk_response(200, 'risk verify 登录失效', {"success": True, "data": {"desc": "risk verify"}}) == (False, "")
    with pytest.raises(LoginRequired):
        checked((False, "[AUTH_REQUIRED] expired", None))
    store.put("xhs_status", {"state": "expired"})
    with store.session() as db:
        job = Job(title="主页", state="running", payload={"sources": [{"url": "https://www.xiaohongshu.com/user/profile/test", "mode": "user"}]})
        ocr = Job(title="ocr", kind="ocr", state="queued")
        paused = Job(title="手动暂停", state="paused")
        db.add_all([job, ocr, paused]); db.flush()
        ids = [job.id, ocr.id, paused.id]
    Runner(store, ids[0]).run()
    with store.session() as db:
        assert [db.get(Job, i).state for i in ids] == ["waiting_login", "queued", "paused"]


def test_ocr_remote_job_resumes_without_resubmitting(env, monkeypatch):
    store, client, data, path = env
    import hashlib
    image = path / "image_0.jpg"
    endpoint = "https://example.invalid/ocr/jobs"
    checkpoint = {"fingerprint": hashlib.sha256(image.read_bytes()).hexdigest(), "url": endpoint, "model": "test-model", "job_id": "existing-job"}
    class FakeResponse:
        status_code = 200
        def json(self):
            return {"data": {"state": "done", "resultUrl": {"jsonUrl": "https://example.invalid/result"}}}
    monkeypatch.setattr("spider_xhs.utils.network.post", lambda *a, **k: pytest.fail("must reuse persisted remote job"))
    monkeypatch.setattr("spider_xhs.utils.network.get", lambda *a, **k: FakeResponse())

    engine = DurableOCR(token="test", model="test-model", async_job_url=endpoint, progress=checkpoint)
    monkeypatch.setattr(engine, "_read_async_result", lambda url: (True, "success", "识别文字"))
    assert engine.parse_image_file(str(image)) == (True, "success", "识别文字")


def test_input_validation():
    assert parse_sources("分享 https://xhslink.com/a/demo")[0]["mode"] == "auto"
    with pytest.raises(ValueError):
        parse_sources("https://example.com/anything")
    with pytest.raises(ValueError):
        parse_sources("https://www.xiaohongshu.com.evil.invalid/explore/demo")


def test_qrcode_persists_credentials_and_resumes_only_waiting_jobs(env, monkeypatch):
    store, client, data, path = env
    login(client)
    from spider_xhs.apis.xhs_pc_login_apis import XHSLoginApi
    cookies = {"a1": "test-a1", "webId": "test-web", "web_session": "test-session"}
    monkeypatch.setattr(XHSLoginApi, "generate_init_cookies", lambda self: cookies)
    monkeypatch.setattr(XHSLoginApi, "generate_qrcode", lambda self, c: (True, "ok", {"qr_id": "qr", "code": "code", "qr_url": "https://example.invalid/qr", "cookies": c}))
    monkeypatch.setattr(XHSLoginApi, "check_qrcode_status", lambda *a: (True, "ok", cookies))
    monkeypatch.setattr(XHSLoginApi, "get_user_info", lambda *a: (True, {"user_id": "test-user", "nickname": "测试昵称"}, cookies))
    store.put("xhs_status", {"state": "expired"})
    with store.session() as db:
        waiting = Job(title="等待登录", state="waiting_login")
        paused = Job(title="主动暂停", state="paused")
        db.add_all([waiting, paused]); db.flush()
        waiting_id, paused_id = waiting.id, paused.id
    qr = client.post("/api/xhs/qrcode").json()
    assert qr["image"].startswith("data:image/png;base64,")
    result = client.get(f"/api/xhs/qrcode/{qr['id']}")
    assert result.json()["state"] == "success", result.text
    assert "test-session" in store.secret("xhs_cookie")
    assert "test-session" not in store.get("xhs_cookie")
    with store.session() as db:
        assert db.get(Job, waiting_id).state == "queued"
        assert db.get(Job, paused_id).state == "paused"


def test_interrupted_download_is_not_exposed_as_finished_file(env, monkeypatch):
    store, client, data, path = env
    login(client)
    (path / "image_0.jpg").unlink()
    job_id = client.post("/api/jobs", json={"input": data["note_url"]}).json()["id"]
    def interrupted(directory, name, url, kind):
        (Path(directory) / (name + ".jpg")).write_bytes(b"incomplete")
        raise RuntimeError("网络中断")
    monkeypatch.setattr("spider_xhs.web.tasks.download_media", interrupted)
    with store.session() as db:
        db.get(Job, job_id).state = "running"
    Runner(store, job_id).run()
    assert not (path / "image_0.jpg").exists()
    assert client.get(f"/api/jobs/{job_id}").json()["state"] == "failed"
    def resumed(directory, name, url, kind):
        target = Path(directory) / (name + ".jpg")
        Image.new("RGB", (60, 80), "green").save(target)
        return str(target)
    monkeypatch.setattr("spider_xhs.web.tasks.download_media", resumed)
    client.post(f"/api/jobs/{job_id}/retry")
    with store.session() as db:
        db.get(Job, job_id).state = "running"
    Runner(store, job_id).run()
    assert (path / "image_0.jpg").exists()
    assert client.get(f"/api/jobs/{job_id}").json()["state"] == "completed"


def test_qrcode_connection_error_is_actionable(env, monkeypatch):
    import requests
    from spider_xhs.apis.xhs_pc_login_apis import XHSLoginApi
    store, client, data, path = env
    login(client)
    def fail(self):
        raise requests.exceptions.SSLError("connection closed")
    monkeypatch.setattr(XHSLoginApi, "generate_init_cookies", fail)
    response = client.post("/api/xhs/qrcode")
    assert response.status_code == 502
    assert "安全连接" in response.json()["detail"]
    assert "官网" in response.json()["detail"]


def test_application_network_does_not_inherit_proxy_environment(monkeypatch):
    import requests
    from spider_xhs.utils import network
    for name in ("HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY", "http_proxy", "https_proxy", "all_proxy"):
        monkeypatch.setenv(name, "http://127.0.0.1:1")
    monkeypatch.setenv("NO_PROXY", "")
    monkeypatch.setenv("no_proxy", "")
    seen = {}
    def send(session, prepared, **kwargs):
        seen.update(kwargs)
        response = requests.Response()
        response.status_code = 200
        response._content = b"ok"
        return response
    monkeypatch.setattr(requests.Session, "send", send)
    assert network.get("https://edith.xiaohongshu.com", timeout=10).status_code == 200
    assert not seen["proxies"]
    assert seen["verify"] is True

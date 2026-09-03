from __future__ import annotations

import base64
import io
import json
import re
import secrets
import shutil
import threading
import time
import zipfile
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Literal
from urllib.parse import urlparse

import qrcode
import requests
from loguru import logger
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError, InvalidHashError
from fastapi import Depends, FastAPI, HTTPException, Request, Response
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field, HttpUrl
from sqlalchemy import delete, func, or_, select
from sqlalchemy.exc import IntegrityError
from starlette.middleware.trustedhost import TrustedHostMiddleware

from spider_xhs.paths import REPO_ROOT
from .db import Folder, Job, JobItem, LoginSession, Note, NoteFolder, NoteTag, Store, User, token_hash, uid
from .library import import_existing, local_path, serialize_note

COOKIE = "xhs_library_session"
LOGIN_VERIFY_ATTEMPTS = 3
LOGIN_VERIFY_TIMEOUT = 45
ph = PasswordHasher()


class Credentials(BaseModel):
    username: str = Field(min_length=1, max_length=80)
    password: str = Field(min_length=8, max_length=256)
    remember: bool = True


class FolderInput(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    parent_id: str | None = None


class Selection(BaseModel):
    note_ids: list[str] = Field(default_factory=list, max_length=10000)
    folder_id: str | None = None


class Organize(Selection):
    action: Literal["add_folder", "remove_folder", "add_tag", "remove_tag", "trash", "restore"]
    value: str = Field(default="", max_length=100)


class CreateJob(Selection):
    kind: Literal["collect", "ocr", "refresh"] = "collect"
    input: str = Field(default="", max_length=20000)
    mode: Literal["auto", "single", "user", "collect", "search"] = "auto"
    limit: int = Field(default=20, ge=0, le=10000)
    save_choice: Literal["all", "media", "media-video", "media-image", "excel"] = "all"
    overwrite: bool = False


class OCRSettings(BaseModel):
    mode: Literal["async", "sync"] = "async"
    model: str = Field(min_length=1, max_length=200)
    url: HttpUrl
    sync_url: HttpUrl
    key: str | None = Field(default=None, max_length=5000)


class ExportSelection(Selection):
    format: Literal["all", "context", "media", "media-image", "media-video", "excel"] = "all"


def create_app(store: Store | None = None):
    store = store or Store()

    @asynccontextmanager
    async def lifespan(app):
        app.state.import_result = import_existing(store)
        app.state.chat.recover()
        try:
            yield
        finally:
            app.state.chat.close()

    app = FastAPI(title="拾页 · 本地素材工作台", lifespan=lifespan)
    app.state.store = store
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=["127.0.0.1", "localhost", "testserver"])
    login_attempts = []
    qr_lock = threading.Lock()
    challenge = {}

    @app.middleware("http")
    async def local_security(request: Request, call_next):
        if request.method not in {"GET", "HEAD", "OPTIONS"}:
            origin = request.headers.get("origin")
            if origin and origin not in {str(request.base_url).rstrip("/"), "http://127.0.0.1:5173", "http://localhost:5173"}:
                return Response("不允许跨站请求", status_code=403)
            if request.headers.get("sec-fetch-site") == "cross-site":
                return Response("不允许跨站请求", status_code=403)
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["X-Frame-Options"] = "DENY"
        if request.url.path.startswith("/api/"):
            response.headers["Cache-Control"] = "no-store"
        return response

    def authenticated(request: Request):
        token = request.cookies.get(COOKIE, "")
        with store.session() as db:
            session = db.get(LoginSession, token_hash(token)) if token else None
            if not session or session.expires_at <= time.time():
                raise HTTPException(401, "请先登录本地工作台")
            return True

    def session_cookie(response, remember):
        value = secrets.token_urlsafe(40)
        age = (30 if remember else 1) * 86400
        with store.session() as db:
            db.add(LoginSession(id=token_hash(value), expires_at=time.time() + age))
            db.execute(delete(LoginSession).where(LoginSession.expires_at < time.time()))
        response.set_cookie(COOKIE, value, httponly=True, samesite="strict", max_age=age if remember else None)

    from .ai import install_chat_routes
    app.state.chat = install_chat_routes(app, store, authenticated)

    @app.get("/api/auth/status")
    def auth_status(request: Request):
        with store.session() as db:
            user = db.get(User, 1)
            token = request.cookies.get(COOKIE)
            session = db.get(LoginSession, token_hash(token)) if token else None
            logged_in = bool(session and session.expires_at > time.time())
            return {"initialized": bool(user), "authenticated": logged_in, "username": user.username if user and logged_in else ""}

    @app.post("/api/auth/setup")
    def setup(data: Credentials, response: Response):
        if not data.username.strip():
            raise HTTPException(422, "用户名不能为空")
        try:
            with store.session() as db:
                if db.get(User, 1):
                    raise HTTPException(409, "管理员已创建，请登录")
                db.add(User(id=1, username=data.username.strip(), password_hash=ph.hash(data.password)))
        except IntegrityError:
            raise HTTPException(409, "管理员已创建，请登录")
        session_cookie(response, data.remember)
        return {"ok": True}

    @app.post("/api/auth/login")
    def login(data: Credentials, response: Response):
        login_attempts[:] = [t for t in login_attempts if t > time.time() - 60]
        if len(login_attempts) >= 8:
            raise HTTPException(429, "尝试次数较多，请一分钟后重试")
        with store.session() as db:
            user = db.get(User, 1)
            try:
                valid = bool(user and user.username == data.username.strip() and ph.verify(user.password_hash, data.password))
            except (VerifyMismatchError, InvalidHashError):
                valid = False
        if not valid:
            login_attempts.append(time.time())
            raise HTTPException(401, "用户名或密码不正确")
        login_attempts.clear()
        session_cookie(response, data.remember)
        return {"ok": True}

    @app.post("/api/auth/logout")
    def logout(request: Request, response: Response, _=Depends(authenticated)):
        with store.session() as db:
            db.execute(delete(LoginSession).where(LoginSession.id == token_hash(request.cookies.get(COOKIE, ""))))
        response.delete_cookie(COOKIE)
        return {"ok": True}

    def get_note(db, note_id):
        note = db.get(Note, note_id)
        if not note:
            raise HTTPException(404, "未找到笔记")
        return note

    def descendants(db, folder_id):
        if not db.get(Folder, folder_id):
            raise HTTPException(404, "文件夹不存在")
        result, frontier = {folder_id}, [folder_id]
        while frontier:
            children = set(db.scalars(select(Folder.id).where(Folder.parent_id.in_(frontier)))) - result
            result.update(children)
            frontier = list(children)
        return result

    def selected_ids(db, data, include_trash=False):
        ids = set(data.note_ids)
        if data.folder_id:
            ids.update(db.scalars(select(NoteFolder.note_id).where(NoteFolder.folder_id.in_(descendants(db, data.folder_id)))))
        query = select(Note.id).where(Note.id.in_(ids))
        if not include_trash:
            query = query.where(Note.trashed_at.is_(None))
        return list(db.scalars(query))

    @app.get("/api/overview", dependencies=[Depends(authenticated)])
    def overview():
        with store.session() as db:
            active = Note.trashed_at.is_(None)
            count = lambda *criteria: db.scalar(select(func.count()).select_from(Note).where(*criteria))
            folders = [{"id": f.id, "name": f.name, "parent_id": f.parent_id,
                        "count": db.scalar(select(func.count()).select_from(NoteFolder).join(Note).where(NoteFolder.folder_id == f.id, active))}
                       for f in db.scalars(select(Folder).order_by(Folder.created_at))]
            originals = set()
            for data in db.scalars(select(Note.data).where(active)):
                originals.update(str(t) for t in data.get("tags", []))
            return {"total": count(active), "images": count(active, Note.kind == "图集"), "videos": count(active, Note.kind == "视频"),
                    "ocr": count(active, Note.ocr_text != ""), "trash": count(Note.trashed_at.is_not(None)), "folders": folders,
                    "tags": list(db.scalars(select(NoteTag.name).distinct().order_by(NoteTag.name))), "original_tags": sorted(originals),
                    "xhs": store.get("xhs_status", {"state": "missing"}), "import_result": getattr(app.state, "import_result", {}),
                    "running_jobs": db.scalar(select(func.count()).select_from(Job).where(Job.state.in_(["queued", "running", "waiting_login"])))}

    @app.post("/api/import", dependencies=[Depends(authenticated)])
    def import_notes():
        return import_existing(store)

    @app.get("/api/notes", dependencies=[Depends(authenticated)])
    def notes(q: str = "", kind: str = "", tag: str = "", original_tag: str = "", folder: str = "", job: str = "", trash: bool = False, page: int = 1, page_size: int = 40, sort: str = "newest"):
        with store.session() as db:
            query = select(Note).where(Note.trashed_at.is_not(None) if trash else Note.trashed_at.is_(None))
            if q:
                query = query.where(or_(Note.search_text.contains(q, autoescape=True), Note.id.in_(select(NoteTag.note_id).where(NoteTag.name.contains(q, autoescape=True)))))
            if kind in {"图集", "视频"}:
                query = query.where(Note.kind == kind)
            if tag:
                query = query.where(Note.id.in_(select(NoteTag.note_id).where(NoteTag.name == tag)))
            if original_tag:
                # JSON text searching would match partial tags; SQLite json_each gives exact membership.
                from sqlalchemy import text
                query = query.where(text("EXISTS (SELECT 1 FROM json_each(notes.data, '$.tags') WHERE value = :original_tag)").bindparams(original_tag=original_tag))
            if folder:
                query = query.where(Note.id.in_(select(NoteFolder.note_id).where(NoteFolder.folder_id == folder)))
            if job:
                query = query.where(Note.id.in_(select(JobItem.note_id).where(JobItem.job_id == job)))
            total = db.scalar(select(func.count()).select_from(query.subquery()))
            ordering = Note.created_at.asc() if sort == "oldest" else Note.updated_at.desc() if sort == "updated" else Note.created_at.desc()
            limit = max(1, min(page_size, 100))
            rows = db.scalars(query.order_by(ordering, Note.id).offset((max(page, 1) - 1) * limit).limit(limit))
            return {"items": [serialize_note(db, store, n) for n in rows], "total": total, "page": page, "page_size": limit}

    @app.get("/api/notes/{note_id}", dependencies=[Depends(authenticated)])
    def detail(note_id: str):
        with store.session() as db:
            return serialize_note(db, store, get_note(db, note_id), detail=True)

    @app.get("/api/media/{note_id}/{relative:path}", dependencies=[Depends(authenticated)])
    def media(note_id: str, relative: str):
        with store.session() as db:
            note = get_note(db, note_id)
            try:
                path = local_path(store, note, relative)
            except ValueError:
                raise HTTPException(404, "文件不存在")
            if not path.is_file() or path.name.startswith(".") or path.suffix == ".part":
                raise HTTPException(404, "文件不存在")
            return FileResponse(path)

    @app.post("/api/folders", dependencies=[Depends(authenticated)])
    def create_folder(data: FolderInput):
        with store.session() as db:
            if not data.name.strip():
                raise HTTPException(422, "文件夹名称不能为空")
            if data.parent_id and not db.get(Folder, data.parent_id):
                raise HTTPException(404, "父文件夹不存在")
            folder = Folder(name=data.name.strip(), parent_id=data.parent_id)
            db.add(folder)
            db.flush()
            return {"id": folder.id}

    @app.patch("/api/folders/{folder_id}", dependencies=[Depends(authenticated)])
    def update_folder(folder_id: str, data: FolderInput):
        with store.session() as db:
            children = descendants(db, folder_id)
            if data.parent_id in children:
                raise HTTPException(422, "不能移动到自身或子文件夹中")
            if data.parent_id and not db.get(Folder, data.parent_id):
                raise HTTPException(404, "父文件夹不存在")
            if not data.name.strip():
                raise HTTPException(422, "名称不能为空")
            folder = db.get(Folder, folder_id)
            folder.name, folder.parent_id = data.name.strip(), data.parent_id
        return {"ok": True}

    @app.delete("/api/folders/{folder_id}", dependencies=[Depends(authenticated)])
    def remove_folder(folder_id: str):
        with store.session() as db:
            descendants(db, folder_id)
            db.delete(db.get(Folder, folder_id))
        return {"ok": True}

    @app.post("/api/organize", dependencies=[Depends(authenticated)])
    def organize(data: Organize):
        with store.session() as db:
            ids = selected_ids(db, data, include_trash=True)
            value = data.value.strip()
            if data.action.endswith("folder") and not db.get(Folder, value):
                raise HTTPException(404, "文件夹不存在")
            if data.action.endswith("tag") and not value:
                raise HTTPException(422, "标签不能为空")
            for note_id in ids:
                if data.action == "add_folder":
                    db.merge(NoteFolder(note_id=note_id, folder_id=value))
                elif data.action == "remove_folder":
                    db.execute(delete(NoteFolder).where(NoteFolder.note_id == note_id, NoteFolder.folder_id == value))
                elif data.action == "add_tag":
                    db.merge(NoteTag(note_id=note_id, name=value))
                elif data.action == "remove_tag":
                    db.execute(delete(NoteTag).where(NoteTag.note_id == note_id, NoteTag.name == value))
                else:
                    db.get(Note, note_id).trashed_at = time.time() if data.action == "trash" else None
        return {"count": len(ids)}

    @app.post("/api/trash/purge", dependencies=[Depends(authenticated)])
    def purge(data: Selection):
        with store.session() as db:
            query = select(Note).where(Note.trashed_at.is_not(None))
            if data.note_ids:
                query = query.where(Note.id.in_(data.note_ids))
            rows = list(db.scalars(query))
            ids = [n.id for n in rows]
            busy = db.scalar(select(func.count()).select_from(JobItem).join(Job).where(JobItem.note_id.in_(ids), Job.state.in_(["queued", "running", "waiting_login", "paused"])))
            if busy:
                raise HTTPException(409, "部分笔记仍关联未结束的任务，请先取消相关任务")
            for note in rows:
                path = local_path(store, note)
                if path.is_dir():
                    shutil.rmtree(path)
                db.delete(note)
        return {"count": len(rows)}

    def job_json(db, job):
        counts = dict(db.execute(select(JobItem.state, func.count()).where(JobItem.job_id == job.id).group_by(JobItem.state)).all())
        return {"id": job.id, "kind": job.kind, "title": job.title, "state": job.state, "message": job.message,
                "created_at": job.created_at, "updated_at": job.updated_at, "counts": counts,
                "total": sum(counts.values()), "done": counts.get("done", 0) + counts.get("skipped", 0), "payload": job.payload}

    @app.get("/api/jobs", dependencies=[Depends(authenticated)])
    def jobs():
        with store.session() as db:
            return [job_json(db, j) for j in db.scalars(select(Job).order_by(Job.created_at.desc()).limit(100))]

    @app.get("/api/jobs/{job_id}", dependencies=[Depends(authenticated)])
    def job_detail(job_id: str):
        with store.session() as db:
            job = db.get(Job, job_id)
            if not job:
                raise HTTPException(404, "任务不存在")
            return {**job_json(db, job), "items": [{"id": i.id, "note_id": i.note_id, "state": i.state, "message": i.message} for i in db.scalars(select(JobItem).where(JobItem.job_id == job_id).limit(1000))]}

    @app.post("/api/jobs", dependencies=[Depends(authenticated)])
    def create_job(data: CreateJob):
        from .tasks import parse_sources
        with store.session() as db:
            payload = data.model_dump()
            ids = selected_ids(db, data)
            if data.kind == "collect":
                try:
                    sources = parse_sources(data.input, data.mode)
                except ValueError as exc:
                    raise HTTPException(422, str(exc))
                payload["sources"] = sources
                title = f"关键词 · {data.input.strip()}" if data.mode == "search" else f"链接采集 · {len(sources)} 个来源"
            else:
                if not ids:
                    raise HTTPException(422, "请先选择笔记")
                if data.kind == "ocr" and not store.secret("ocr_key"):
                    raise HTTPException(422, "请先在设置中填写 OCR Key")
                title = f"{'文字识别' if data.kind == 'ocr' else '刷新笔记'} · {len(ids)} 条笔记"
            job = Job(kind=data.kind, title=title, payload=payload)
            db.add(job)
            db.flush()
            for note_id in ids:
                note = db.get(Note, note_id)
                db.add(JobItem(job_id=job.id, item_key=note_id, note_id=note_id, url=note.data.get("note_url", "")))
            return {"id": job.id}

    @app.post("/api/jobs/{job_id}/{action}", dependencies=[Depends(authenticated)])
    def control_job(job_id: str, action: Literal["pause", "resume", "cancel", "retry"]):
        with store.session() as db:
            job = db.get(Job, job_id)
            if not job:
                raise HTTPException(404, "任务不存在")
            if action == "pause":
                if job.state not in {"running", "queued", "waiting_login"}:
                    raise HTTPException(409, "任务当前无法暂停")
                job.state, job.message = "paused", "已主动暂停，将在当前操作完成后停下"
            elif action == "cancel":
                job.state, job.message = "cancelled", "已取消，已完成的素材保留"
            elif action == "resume":
                if job.state not in {"paused", "waiting_login", "failed"}:
                    raise HTTPException(409, "任务当前无法继续")
                job.state, job.message = "queued", "等待继续"
            else:
                for item in db.scalars(select(JobItem).where(JobItem.job_id == job_id, JobItem.state == "failed")):
                    item.state, item.message = "pending", "等待重试"
                job.state, job.message = "queued", "等待重试未完成部分"
            job.updated_at = time.time()
        return {"ok": True}

    @app.get("/api/settings/ocr", dependencies=[Depends(authenticated)])
    def ocr_settings():
        return {**store.get("ocr", {}), "has_key": bool(store.secret("ocr_key"))}

    @app.put("/api/settings/ocr", dependencies=[Depends(authenticated)])
    def save_ocr_settings(data: OCRSettings):
        store.put("ocr", data.model_dump(mode="json", exclude={"key"}))
        if data.key is not None and data.key.strip():
            store.put_secret("ocr_key", data.key.strip())
        return {"ok": True}

    @app.post("/api/settings/ocr/test", dependencies=[Depends(authenticated)])
    def test_ocr():
        from PIL import Image, ImageDraw
        from .tasks import build_ocr
        path = store.root / f"ocr-test-{uid()}.png"
        image = Image.new("RGB", (400, 100), "white")
        ImageDraw.Draw(image).text((20, 25), "HELLO 123", fill="black", font_size=32)
        image.save(path)
        try:
            ok, msg, text = build_ocr(store).parse_image_file(str(path))
            return {"ok": bool(ok and text.strip()), "message": "连接成功，测试图片识别完成" if ok and text.strip() else "服务未能识别测试图片，请检查地址、模型和 Key"}
        except Exception:
            raise HTTPException(502, "OCR 测试失败，请检查服务地址、模型、Key 或网络")
        finally:
            path.unlink(missing_ok=True)

    @app.get("/api/xhs/status", dependencies=[Depends(authenticated)])
    def xhs_status():
        return store.get("xhs_status", {"state": "missing"})

    @app.post("/api/xhs/check", dependencies=[Depends(authenticated)])
    def xhs_check():
        from .tasks import verify_cookie
        try:
            verify_cookie(store)
        except Exception:
            pass
        return store.get("xhs_status", {"state": "missing"})

    @app.post("/api/xhs/qrcode", dependencies=[Depends(authenticated)])
    def create_qrcode():
        from spider_xhs.apis.xhs_pc_login_apis import XHSLoginApi
        with qr_lock:
            api = XHSLoginApi()
            stage = "initial_cookie"
            try:
                cookies = api.generate_init_cookies()
                stage = "create_qr"
                ok, msg, data = api.generate_qrcode(cookies)
                if not ok:
                    raise ValueError(str(msg) or "二维码生成失败")
                buffer = io.BytesIO()
                qrcode.make(data["qr_url"]).save(buffer, format="PNG")
                challenge.clear()
                challenge.update({"id": uid(), "data": data, "created": time.time()})
                return {"id": challenge["id"], "image": "data:image/png;base64," + base64.b64encode(buffer.getvalue()).decode()}
            except requests.exceptions.SSLError as exc:
                from .tasks import public_error
                logger.warning("QR login HTTPS failure at {}: {}", stage, public_error(exc))
                raise HTTPException(502, "无法与小红书建立安全连接。请先在常用浏览器打开小红书；若官网提示安全限制或 IP 风险，请按官网提示处理后再试。")
            except requests.RequestException:
                raise HTTPException(502, "连接小红书失败，请检查网络，并确认小红书官网可以正常登录。")
            except ValueError as exc:
                from .tasks import public_error
                raise HTTPException(502, public_error(exc))
            except Exception:
                raise HTTPException(502, "二维码生成失败，请确认小红书官网可以正常登录后重试。")

    @app.get("/api/xhs/qrcode/{challenge_id}", dependencies=[Depends(authenticated)])
    def poll_qrcode(challenge_id: str):
        from spider_xhs.apis.xhs_pc_login_apis import XHSLoginApi
        with qr_lock:
            if challenge.get("id") != challenge_id:
                return {"state": "expired", "message": "二维码已过期，请重新生成"}
            if challenge.get("result"):
                return challenge["result"]

            def finish(state, message):
                result = {"state": state, "message": message}
                challenge["result"] = result
                challenge.pop("data", None)
                return result

            if time.time() - challenge.get("created", 0) > 240:
                return finish("expired", "二维码已过期，请重新生成")
            api, data = XHSLoginApi(), challenge["data"]

            def connected(user):
                store.put("xhs_status", {"state": "valid", "nickname": user.get("nickname", "已登录"),
                    "user_id": str(user.get("user_id") or user.get("id")), "checked_at": time.time()})
                with store.session() as db:
                    for job in db.scalars(select(Job).where(Job.state == "waiting_login")):
                        job.state, job.message = "queued", "登录已恢复，等待继续"

            def blocked(message):
                # A rejected QR request does not invalidate a previously saved
                # session. Reuse it only after a fresh, same-account check.
                previous = store.get("xhs_status", {})
                saved_cookie = store.secret("xhs_cookie")
                if saved_cookie and previous.get("user_id"):
                    from spider_xhs.utils.cookie_util import trans_cookies
                    try:
                        saved_fields = trans_cookies(saved_cookie)
                        if saved_fields.get("a1") and saved_fields.get("web_session"):
                            valid, user, _ = XHSLoginApi().get_user_info(saved_fields)
                            user_id = str(user.get("user_id") or user.get("id") or "")
                            if valid and user.get("guest") in (False, 0, 'false', '0') and user_id == previous["user_id"]:
                                connected(user)
                                return finish("success", "本次扫码请求受限；已确认原账号的登录仍有效，继续使用已保存的登录。")
                    except Exception:
                        pass
                return finish("blocked", message)

            def verification_retry(message):
                attempts = data.get("verification_attempts", 0)
                elapsed = time.time() - data.get("verification_started", time.time())
                if attempts >= LOGIN_VERIFY_ATTEMPTS or elapsed >= LOGIN_VERIFY_TIMEOUT:
                    return finish("error", f"扫码已确认，但账号校验未完成：{message} 请重新生成二维码。")
                return {"state": "verifying", "message": f"扫码已确认，正在重试账号校验（{attempts}/{LOGIN_VERIFY_ATTEMPTS}）：{message}"}

            try:
                if not data.get("confirmed"):
                    ok, message, cookies = api.check_qrcode_status(data["qr_id"], data["code"], data["cookies"])
                    data["cookies"] = cookies
                    if not ok:
                        issue = api.last_auth_issue or {}
                        if issue.get("kind") == "blocked" or any(word in str(message) for word in ("IP存在风险", "IP 存在风险", "安全限制", "访问过于频繁", "需要验证")):
                            return blocked(issue.get("message") or "小红书限制了当前登录请求，请先在官网处理后重新扫码。")
                        if issue:
                            return finish("error", issue["message"])
                        if "过期" in str(message):
                            return finish("expired", message)
                        return {"state": "waiting", "message": message}
                    data["confirmed"] = True
                    data["verification_started"] = time.time()
                    data["verification_attempts"] = 0
                cookies = data["cookies"]
                if not cookies.get("web_session"):
                    return finish("error", "手机已确认，但登录凭据没有交换成功，请重新生成二维码。")
                if data.get("verification_attempts", 0) >= LOGIN_VERIFY_ATTEMPTS or time.time() - data["verification_started"] >= LOGIN_VERIFY_TIMEOUT:
                    return finish("error", "账号校验超时，请检查网络后重新生成二维码。")
                data["verification_attempts"] += 1
                valid, user, cookies = api.get_user_info(cookies)
                data["cookies"] = cookies
                if not valid:
                    issue = api.last_auth_issue or {}
                    if issue.get("kind") == "blocked":
                        return blocked(issue["message"])
                    if issue.get("kind") in {"authentication", "protocol"}:
                        return finish("error", issue["message"])
                    return verification_retry(issue.get("message") or "小红书暂未返回有效账号信息。")
                if not cookies.get("web_session") or user.get("guest") in (True, 1, 'true', '1'):
                    return finish("error", "小红书未确认有效登录，请重新扫码并在手机上确认。")
                user_id = str(user.get("user_id") or user.get("id") or "")
                if not user_id:
                    return finish("error", "账号校验未返回用户信息，请重新扫码。")
                previous = store.get("xhs_status", {})
                if previous.get("user_id") and user_id and previous["user_id"] != user_id:
                    return finish("error", "请使用原小红书账号扫码，以恢复该账号的采集任务")
                store.put_secret("xhs_cookie", api.cookies_to_str(cookies))
                connected(user)
                return finish("success", "登录成功，已保存凭据并恢复等待中的任务")
            except requests.RequestException:
                if data.get("confirmed"):
                    return verification_retry("连接账号校验服务失败。")
                raise HTTPException(502, "查询扫码状态失败，请检查直连网络后重试。")
            except Exception:
                return finish("error", "账号校验未完成，请重新生成二维码或稍后重试。")

    @app.post("/api/exports", dependencies=[Depends(authenticated)])
    def export_notes(data: ExportSelection):
        from spider_xhs.utils.data_util import save_to_xlsx
        export_dir = store.root / "exports"
        export_dir.mkdir(exist_ok=True)
        for old in export_dir.glob("*"):
            if old.is_file() and old.stat().st_mtime < time.time() - 86400:
                old.unlink(missing_ok=True)
        with store.session() as db:
            ids = selected_ids(db, data)
            if not ids:
                raise HTTPException(422, "请先选择笔记或文件夹")
            rows = list(db.scalars(select(Note).where(Note.id.in_(ids))))
            name = uid() + (".xlsx" if data.format == "excel" else ".zip")
            target = export_dir / name
            if data.format == "excel":
                save_to_xlsx([n.data for n in rows], str(target))
            else:
                with zipfile.ZipFile(target, "w", zipfile.ZIP_DEFLATED, compresslevel=1) as archive:
                    for note in rows:
                        base = local_path(store, note)
                        for p in base.rglob("*"):
                            if not p.is_file() or p.is_symlink() or p.name.startswith(".") or p.suffix == ".part":
                                continue
                            relative = p.relative_to(base)
                            if data.format == "context" and (p.suffix not in {".txt", ".json", ".md"}):
                                continue
                            if data.format == "media-image" and p.suffix.lower() not in {".png", ".jpg", ".jpeg", ".webp", ".avif"}:
                                continue
                            if data.format == "media-video" and p.suffix.lower() not in {".mp4", ".mp3", ".wav"}:
                                continue
                            archive.write(p, f"{note.id}/{relative}")
                        if data.format == "all":
                            pass
                    if data.format == "all":
                        xlsx = export_dir / f"{uid()}.xlsx"
                        try:
                            save_to_xlsx([n.data for n in rows], str(xlsx))
                            archive.write(xlsx, "笔记汇总.xlsx")
                        finally:
                            xlsx.unlink(missing_ok=True)
        return {"url": f"/api/exports/{name}", "name": f"拾页-{len(ids)}条笔记{target.suffix}"}

    @app.get("/api/exports/{filename}", dependencies=[Depends(authenticated)])
    def export_file(filename: str):
        if not re.fullmatch(r"[a-f0-9]{32}\.(zip|xlsx)", filename):
            raise HTTPException(404)
        path = store.root / "exports" / filename
        if not path.is_file():
            raise HTTPException(404, "导出文件已过期，请重新导出")
        return FileResponse(path, filename=f"拾页导出{path.suffix}")

    frontend = REPO_ROOT / "frontend/dist"
    if frontend.exists():
        app.mount("/assets", StaticFiles(directory=frontend / "assets"), name="assets")

        @app.get("/{path:path}")
        def index(path: str):
            if path.startswith("api/"):
                raise HTTPException(404)
            return FileResponse(frontend / "index.html")

    return app

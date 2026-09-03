from __future__ import annotations

import hashlib
import json
import os
import re
import time
from pathlib import Path
from urllib.parse import parse_qs, urlencode, urlparse

from spider_xhs.utils import network as requests
from PIL import Image
from sqlalchemy import select

from spider_xhs.apis.xhs_pc_apis import XHS_Apis
from spider_xhs.utils.cookie_util import trans_cookies
from spider_xhs.utils.data_util import (collect_note_image_files, download_media, extract_audio_from_video,
    handle_note_info, norm_str, save_ai_context, save_note_detail, save_to_xlsx)
from spider_xhs.utils.ocr_util import OCRClient
from .db import Job, JobItem, Note
from .library import IMAGE_EXTS, index_note, local_path


class TaskStopped(Exception):
    pass


class LoginRequired(Exception):
    pass


class PlatformBlocked(Exception):
    pass


def public_error(error):
    text = re.sub(r"https?://\S+", "[请求地址]", str(error))
    return re.sub(r"[A-Za-z0-9_\-+/=]{64,}", "[已隐藏]", text)[:350]


def parse_sources(raw, mode="auto"):
    if mode == "search":
        if not raw.strip():
            raise ValueError("请输入搜索关键词")
        return [{"url": raw.strip(), "mode": "search"}]
    urls = re.findall(r"https?://[^\s，,]+", raw)
    if not urls:
        raise ValueError("请输入小红书笔记、作者、收藏链接或分享文案")
    if len(urls) > 100:
        raise ValueError("一次最多提交 100 个链接")
    result = []
    for url in dict.fromkeys(urls):
        url = url.rstrip('。；：！？、\"\'”’）)')
        validate_url(url)
        result.append({"url": url, "mode": mode})
    return result


def validate_url(url):
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"} or parsed.hostname not in {"xiaohongshu.com", "www.xiaohongshu.com", "xhslink.com", "www.xhslink.com"} or parsed.username or parsed.port not in {None, 80, 443}:
        raise ValueError("仅支持小红书网页链接和 xhslink 分享链接")


class WebXHS(XHS_Apis):
    def __init__(self, check=lambda: None):
        super().__init__()
        self.check = check

    def _request_json(self, *args, **kwargs):
        self.check()
        return super()._request_json(*args, **kwargs)

    def _is_risk_response(self, status_code, response_text, res_json=None):
        message = str((res_json or {}).get("msg", "")) if isinstance(res_json, dict) else ""
        code = str(res_json.get("code", "")) if isinstance(res_json, dict) else ""
        if status_code in {461, 471} or code == "300012" or any(word in message for word in ("IP存在风险", "IP 存在风险", "安全限制")):
            return True, "[PLATFORM_BLOCKED] 小红书限制当前网络访问，请先在官网处理网络或验证"
        if status_code == 401 or any(t in message.lower() for t in ("未登录", "登录失效", "登录已失效", "登录已过期", "登录过期", "登录态失效", "请先登录", "session expired", "login required")):
            return True, "[AUTH_REQUIRED] 小红书登录已失效"
        if status_code < 400 and isinstance(res_json, dict) and res_json.get("success") is True:
            return False, ""
        # Inspect error messages, never user-authored text in a successful note.
        return super()._is_risk_response(status_code, message if isinstance(res_json, dict) else response_text, res_json)


def checked(result):
    ok, msg, data = result
    if ok:
        return data
    message = str(msg)
    if "[AUTH_REQUIRED]" in message:
        raise LoginRequired("小红书登录已失效，请扫码继续")
    if "[TASK_STOPPED]" in message:
        raise TaskStopped(message)
    if "[PLATFORM_BLOCKED]" in message or "风控" in message or "验证码" in message or "访问过于频繁" in message:
        raise PlatformBlocked("小红书要求验证或限制当前网络访问，请先在官网按提示处理，再手动继续任务")
    raise RuntimeError(public_error(message) or "接口没有返回有效数据")


def verify_cookie(store, check=lambda: None):
    cookie = store.secret("xhs_cookie")
    fields = trans_cookies(cookie)
    if not fields.get("a1") or not fields.get("web_session"):
        store.put("xhs_status", {**store.get("xhs_status", {}), "state": "expired"})
        raise LoginRequired("请先扫码登录小红书")
    try:
        response = checked(WebXHS(check).get_user_self_info2(cookie))
        data = response.get("data") or {}
        if data.get("guest") in (True, 1, 'true', '1') or not (data.get("user_id") or data.get("id")):
            raise LoginRequired("小红书返回游客会话或缺少账号信息，请重新扫码登录")
        store.put("xhs_status", {"state": "valid", "nickname": data.get("nickname", "已登录"),
                  "user_id": str(data.get("user_id") or data.get("id") or ""), "checked_at": time.time()})
    except LoginRequired:
        store.put("xhs_status", {**store.get("xhs_status", {}), "state": "expired"})
        raise
    except (PlatformBlocked, RuntimeError):
        store.put("xhs_status", {**store.get("xhs_status", {}), "state": "error"})
        raise
    return cookie


def atomic_text(path, text):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name("." + path.name + ".part")
    temporary.write_text(text, encoding="utf-8")
    os.replace(temporary, path)


class DurableOCR(OCRClient):
    """Keep the server-side job ID so a restarted worker can resume polling."""
    def __init__(self, *args, progress=None, save=None, check=lambda: None, **kwargs):
        super().__init__(*args, **kwargs)
        self.progress, self.save, self.check = progress or {}, save or (lambda value: None), check

    def _sleep_interruptibly(self, seconds):
        end = time.monotonic() + seconds
        while time.monotonic() < end:
            self.check()
            time.sleep(min(0.25, max(0, end - time.monotonic())))

    def _parse_image_async(self, file_path):
        self.check()
        fingerprint = hashlib.sha256(Path(file_path).read_bytes()).hexdigest()
        identity = {"fingerprint": fingerprint, "url": self.async_job_url, "model": self.model}
        checkpoint = self.progress
        job_id = checkpoint.get("job_id") if all(checkpoint.get(k) == v for k, v in identity.items()) else None
        headers = {"Authorization": f"bearer {self.token}"}
        if not job_id:
            for attempt in range(self.submit_retries + 1):
                self.check()
                with open(file_path, "rb") as f:
                    response = requests.post(self.async_job_url, headers=headers, data={"model": self.model,
                        "optionalPayload": json.dumps(self.optional_payload)}, files={"file": f}, timeout=120)
                if response.status_code == 200:
                    break
                if not self._is_queue_full_response(response) or attempt == self.submit_retries:
                    return False, f"OCR 提交失败（HTTP {response.status_code}），请检查设置或服务额度", ""
                self._sleep_interruptibly(min(self.submit_retry_delay * (attempt + 1), 180))
            job_id = response.json().get("data", {}).get("jobId")
            if not job_id:
                return False, "OCR 服务未返回任务 ID", ""
            self.save({**identity, "job_id": job_id})
        started = time.monotonic()
        while time.monotonic() - started < self.timeout_seconds:
            self.check()
            response = requests.get(f"{self.async_job_url.rstrip('/')}/{job_id}", headers=headers, timeout=60)
            if response.status_code in {401, 403}:
                return False, "OCR Key 无效或无权限，请更新设置", ""
            if response.status_code in {404, 410}:
                self.save({})
                return False, "服务端 OCR 任务已过期，可点击重试重新提交", ""
            if response.status_code == 200:
                data = response.json().get("data") or {}
                state = data.get("state")
                if state == "done":
                    url = data.get("resultUrl", {}).get("jsonUrl")
                    return self._read_async_result(url) if url else (False, "OCR 服务未提供结果地址", "")
                if state == "failed":
                    self.save({})
                    return False, "OCR 服务处理失败，可重试", ""
                if state not in {"pending", "running"}:
                    return False, "OCR 服务返回未知任务状态", ""
            self._sleep_interruptibly(self.poll_interval)
        return False, "OCR 等待超时，点击重试可继续查询同一个服务端任务", ""


def build_ocr(store, **kwargs):
    settings = store.get("ocr", {})
    return DurableOCR(token=store.secret("ocr_key"), mode=settings.get("mode", "async"),
        model=settings.get("model", "PaddleOCR-VL-1.6"), async_job_url=settings.get("url", ""), sync_url=settings.get("sync_url", ""), **kwargs)


class Runner:
    def __init__(self, store, job_id, stopping=lambda: False):
        self.store, self.job_id, self.stopping = store, job_id, stopping
        self.api = WebXHS(self.check)

    def check(self):
        with self.store.session() as db:
            job = db.get(Job, self.job_id)
            if self.stopping() or not job or job.state != "running":
                raise TaskStopped("[TASK_STOPPED] 任务已暂停或取消")

    def cookie(self):
        self.check()
        status = self.store.get("xhs_status", {})
        if status.get("state") in {"missing", "expired"}:
            raise LoginRequired("请扫码登录小红书")
        if status.get("state") != "valid" or time.time() - status.get("checked_at", 0) > 600:
            return verify_cookie(self.store, self.check)
        return self.store.secret("xhs_cookie")

    def item_checkpoint(self, item_id, key, value):
        with self.store.session() as db:
            item = db.get(JobItem, item_id)
            item.checkpoint = {**item.checkpoint, key: value}

    def message(self, text):
        with self.store.session() as db:
            job = db.get(Job, self.job_id)
            if job.state == "running":
                job.message, job.updated_at = text, time.time()

    def discover_page(self):
        self.check()
        with self.store.session() as db:
            job = db.get(Job, self.job_id)
            payload, cp = dict(job.payload), dict(job.checkpoint)
        sources = payload.get("sources", [])
        index = cp.get("source_index", 0)
        if index >= len(sources):
            return True
        source = sources[index]
        mode = source["mode"]
        url = source["url"]
        if mode != "search":
            url = self.api._resolve_share_url(url)
            validate_url(url)
            parsed = urlparse(url)
            params = parse_qs(parsed.query)
            if mode == "auto":
                mode = ("collect" if params.get("tab") == ["fav"] else "user") if "/user/profile/" in parsed.path else "single"
        else:
            parsed, params = None, {}
        cursor, page = cp.get("cursor", ""), cp.get("page", 1)
        limit, seen = payload.get("limit", 20), cp.get("seen", 0)
        next_cursor = ""
        if mode == "single":
            note_id = parsed.path.rstrip("/").split("/")[-1]
            rows = [(note_id, url)]
            done = True
        else:
            cookie = self.cookie()
            if mode == "search":
                data = checked(self.api.search_note(url, cookie, page=page)).get("data") or {}
                notes = [n for n in data.get("items", []) if n.get("model_type") == "note"]
                next_cursor = str(page + 1)
            else:
                user_id = parsed.path.rstrip("/").split("/")[-1]
                call = self.api.get_user_collect_note_info if mode == "collect" else self.api.get_user_note_info
                data = checked(call(user_id, cursor, cookie, params.get("xsec_token", [""])[0], params.get("xsec_source", ["pc_user"])[0])).get("data") or {}
                notes = data.get("notes", [])
                next_cursor = str(data.get("cursor", ""))
            if limit:
                notes = notes[:max(0, limit - seen)]
            rows = []
            for note in notes:
                note_id = str(note.get("note_id") or note.get("id") or "")
                if note_id:
                    rows.append((note_id, f"https://www.xiaohongshu.com/explore/{note_id}?" + urlencode({"xsec_token": note.get("xsec_token", "")})))
            done = not data.get("has_more") or (limit > 0 and seen + len(notes) >= limit)
            if not done and mode != "search" and (not next_cursor or next_cursor == cursor):
                raise RuntimeError("分页游标未前进，已停止以避免重复请求")
        self.check()
        with self.store.session() as db:
            for note_id, note_url in rows:
                key = note_id or hashlib.sha256(note_url.encode()).hexdigest()
                existed = db.scalar(select(JobItem.id).where(JobItem.job_id == self.job_id, JobItem.item_key == key))
                if not existed:
                    db.add(JobItem(job_id=self.job_id, item_key=key, note_id=note_id, url=note_url))
            job = db.get(Job, self.job_id)
            job.checkpoint = {"source_index": index + 1, "cursor": "", "seen": 0, "page": 1} if done else {
                "source_index": index, "cursor": next_cursor, "seen": seen + len(rows), "page": page + 1}
        return done and index + 1 >= len(sources)

    def download(self, note, old_data, payload):
        base = local_path(self.store, note)
        base.mkdir(parents=True, exist_ok=True)
        staging = base / ".partial"
        staging.mkdir(exist_ok=True)
        changed = False
        data, choice = note.data, payload.get("save_choice", "all")
        force = payload.get("kind") == "refresh"
        old_images = old_data.get("image_list", [])

        def image(name, source, old_source):
            nonlocal changed
            self.check()
            existing = [p for p in base.glob(name + ".*") if p.suffix in IMAGE_EXTS and p.stat().st_size > 0]
            if existing and not (force and old_source != source):
                original = existing[0]
            else:
                original_temp = Path(download_media(str(staging), name, source, "image"))
                with Image.open(original_temp) as im:
                    im.verify()
                original = base / original_temp.name
                os.replace(original_temp, original)
                for p in existing:
                    if p != original:
                        p.unlink(missing_ok=True)
                changed = True
            self.check()
            png = base / "png" / f"{name}.png"
            if not png.exists() or (force and old_source != source):
                png.parent.mkdir(exist_ok=True)
                temp = png.with_suffix(".part")
                with Image.open(original) as im:
                    im.convert("RGBA").save(temp, format="PNG")
                os.replace(temp, png)
                changed = True

        if choice != "excel":
            if note.kind == "图集" and choice in {"all", "media", "media-image"}:
                for i, source in enumerate(data.get("image_list", [])):
                    image(f"image_{i}", source, old_images[i] if i < len(old_images) else "")
            if note.kind == "视频" and choice in {"all", "media", "media-video"}:
                if data.get("video_cover"):
                    image("cover", data["video_cover"], old_data.get("video_cover"))
                self.check()
                target = base / "video_files/video.mp4"
                target.parent.mkdir(exist_ok=True)
                if not target.is_file() or target.stat().st_size == 0 or (force and old_data.get("video_addr") != data.get("video_addr")):
                    temp = Path(download_media(str(staging), "video", data.get("video_addr"), "video"))
                    if temp.stat().st_size == 0:
                        raise RuntimeError("视频下载为空")
                    os.replace(temp, target)
                    changed = True
                self.check()
                if force or not any((target.parent / name).is_file() for name in ("audio.mp3", "audio.wav")):
                    extract_audio_from_video(str(target))
        self.check()
        atomic_text(base / "info.json", json.dumps(data, ensure_ascii=False))
        save_note_detail(data, str(base))
        if note.kind == "视频" and (base / "video_files/video.mp4").exists():
            with open(base / "detail.txt", "a", encoding="utf-8") as f:
                f.write("本地视频文件: video_files/video.mp4\n")
                for name in ("audio.mp3", "audio.wav"):
                    if (base / "video_files" / name).exists():
                        f.write(f"本地音频文件: video_files/{name}\n")
        save_ai_context(data, str(base))
        return changed

    def process_collect(self, item, job):
        with self.store.session() as db:
            existing = db.get(Note, item.note_id)
            if existing and existing.trashed_at:
                return "skipped", "笔记位于回收站，保持原状态"
            old_data = dict(existing.data) if existing else {}
        if not existing or job.kind == "refresh":
            self.message("正在获取笔记详情")
            data = checked(self.api.get_note_info(item.url, self.cookie()))
            source = data.get("data", {}).get("items", [])
            if not source:
                raise RuntimeError("笔记详情为空，可能已删除或不可见")
            row = {**source[0], "url": item.url}
            info = handle_note_info(row)
            if existing:
                path = Path(existing.path)
            else:
                title = norm_str(info.get("title", "无标题"))[:40] or "无标题"
                author = norm_str(info.get("nickname", "未知作者"))[:20]
                path = self.store.media / f"{author}_{info['user_id']}" / f"{title}_{info['note_id']}"
            path.mkdir(parents=True, exist_ok=True)
            with self.store.session() as db:
                existing = index_note(db, self.store, info, path, refresh=True)
                db.get(JobItem, item.id).note_id = existing.id
            # A crash after indexing is recoverable from this metadata even before all media arrive.
            atomic_text(path / "info.json", json.dumps(info, ensure_ascii=False))
        self.message(f"正在整理 · {existing.title}")
        changed = self.download(existing, old_data, {**job.payload, "kind": job.kind})
        with self.store.session() as db:
            index_note(db, self.store, existing.data, existing.path, refresh=True)
        return ("skipped", "已入库，文件齐全") if old_data and not changed and job.kind != "refresh" else ("done", "已保存")

    def process_ocr(self, item, job):
        with self.store.session() as db:
            note = db.get(Note, item.note_id)
        if not note or note.trashed_at:
            return "skipped", "笔记已移入回收站或不存在"
        base = local_path(self.store, note)
        files = collect_note_image_files(str(base))
        if not files:
            raise RuntimeError("笔记没有本地图片，请先补齐下载")
        for file in files:
            self.check()
            path = Path(file)
            self.message(f"正在识别 · {note.title} / {path.name}")
            with self.store.session() as db:
                cp = dict(db.get(JobItem, item.id).checkpoint)
            target = base / "ocr" / f"{path.stem}.md"
            fingerprint = hashlib.sha256(path.read_bytes()).hexdigest()
            complete_key = "done:" + path.name
            if target.exists() and target.stat().st_size and (not job.payload.get("overwrite") or cp.get(complete_key) == fingerprint):
                continue
            client = build_ocr(self.store, progress=cp.get(path.name), save=lambda value: self.item_checkpoint(item.id, path.name, value), check=self.check)
            ok, message, text = client.parse_image_file(file)
            self.check()
            if not ok or not text.strip():
                raise RuntimeError(message or "OCR 未返回文字")
            atomic_text(target, text)
            self.item_checkpoint(item.id, complete_key, fingerprint)
            save_ai_context(note.data, str(base))
            with self.store.session() as db:
                index_note(db, self.store, note.data, base, refresh=True)
        save_ai_context(note.data, str(base))
        with self.store.session() as db:
            index_note(db, self.store, note.data, base, refresh=True)
        return "done", "文字识别完成"

    def process_pending(self):
        while True:
            self.check()
            with self.store.session() as db:
                item = db.scalar(select(JobItem).where(JobItem.job_id == self.job_id, JobItem.state == "pending"))
                job = db.get(Job, self.job_id)
                if not item:
                    return
                item.state = "running"
            try:
                state, message = self.process_ocr(item, job) if job.kind == "ocr" else self.process_collect(item, job)
            except (TaskStopped, LoginRequired, PlatformBlocked):
                with self.store.session() as db:
                    db.get(JobItem, item.id).state = "pending"
                raise
            except Exception as exc:
                state, message = "failed", public_error(exc)
            with self.store.session() as db:
                current = db.get(JobItem, item.id)
                current.state, current.message = state, message

    def run(self):
        try:
            with self.store.session() as db:
                job = db.get(Job, self.job_id)
            if job.kind == "collect":
                while True:
                    self.process_pending()
                    if self.discover_page():
                        self.process_pending()
                        break
            else:
                self.process_pending()
            self.check()
            with self.store.session() as db:
                job = db.get(Job, self.job_id)
                if job.state != "running":
                    return
                items = list(db.scalars(select(JobItem).where(JobItem.job_id == job.id)))
                ids = [i.note_id for i in items if i.state in {"done", "skipped"}]
                rows = list(db.scalars(select(Note).where(Note.id.in_(ids), Note.trashed_at.is_(None))))
            if job.kind != "ocr" and job.payload.get("save_choice") in {"all", "excel"} and rows:
                target = self.store.excel / f"采集_{job.id[:8]}.xlsx"
                save_to_xlsx([n.data for n in rows], str(target))
            failures = sum(i.state == "failed" for i in items)
            with self.store.session() as db:
                job = db.get(Job, self.job_id)
                if job.state != "running":
                    return
                job.state = "failed" if failures else "completed"
                job.message = f"{failures} 条处理失败，可重试失败项" if failures else f"处理完成，共 {len(items)} 条笔记"
                job.updated_at = time.time()
        except TaskStopped:
            pass
        except LoginRequired:
            self.store.put("xhs_status", {**self.store.get("xhs_status", {}), "state": "expired"})
            with self.store.session() as db:
                for job in db.scalars(select(Job).where(Job.kind != "ocr", Job.state.in_(["queued", "running"]))):
                    job.state, job.message = "waiting_login", "小红书登录失效，请扫码后继续"
        except PlatformBlocked as exc:
            with self.store.session() as db:
                job = db.get(Job, self.job_id)
                if job.state == "running":
                    job.state, job.message = "paused", str(exc)
        except Exception as exc:
            with self.store.session() as db:
                job = db.get(Job, self.job_id)
                if job.state == "running":
                    job.state, job.message = "failed", public_error(exc)

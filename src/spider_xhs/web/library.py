from __future__ import annotations

import json
import re
import time
from pathlib import Path
from urllib.parse import quote

from sqlalchemy import select

from .db import Note, NoteFolder, NoteTag

IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".webp", ".avif"}


def natural_key(path):
    return [int(s) if s.isdigit() else s for s in re.split(r"(\d+)", path.name)]


def local_path(store, note, relative=""):
    base = Path(note.path).resolve()
    if not base.is_relative_to(store.media) or base == store.media:
        raise ValueError("素材路径不在配置目录中")
    path = (base / relative).resolve()
    if not path.is_relative_to(base):
        raise ValueError("无效的文件路径")
    return path


def read_ocr(base):
    from spider_xhs.utils.data_util import clean_ocr_text
    texts = []
    for p in sorted((base / "ocr").glob("*.md"), key=natural_key):
        if p.is_symlink():
            continue
        try:
            value = clean_ocr_text(p.read_text(encoding="utf-8"))
            if value:
                texts.append(f"[{p.name}]\n{value}")
        except (OSError, UnicodeError):
            pass
    return "\n\n".join(texts)


def index_note(db, store, data, path, *, refresh=False):
    note_id = str(data.get("note_id") or "")
    if not re.fullmatch(r"[A-Za-z0-9_-]{1,128}", note_id):
        raise ValueError("缺少有效的笔记 ID")
    path = Path(path).resolve()
    if path == store.media or not path.is_relative_to(store.media):
        raise ValueError("素材路径不在配置目录中")
    note = db.get(Note, note_id)
    if note is None:
        note = Note(id=note_id, created_at=path.stat().st_mtime if path.exists() else time.time())
        db.add(note)
    elif not refresh:
        return note
    note.title = str(data.get("title") or "无标题")
    note.author = str(data.get("nickname") or "未知作者")
    note.kind = "视频" if data.get("note_type") == "视频" else "图集"
    note.data = data
    note.path = str(path)
    note.ocr_text = read_ocr(path)
    note.search_text = "\n".join([note.title, note.author, str(data.get("desc", "")), " ".join(str(t) for t in data.get("tags", [])), note.ocr_text])
    note.updated_at = time.time()
    return note


def import_existing(store):
    imported, invalid = 0, 0
    for p in store.media.rglob("info.json"):
        if p.is_symlink() or not p.resolve().is_relative_to(store.media):
            continue
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
            with store.session() as db:
                existed = db.get(Note, str(data.get("note_id", ""))) is not None
                index_note(db, store, data, p.parent)
                imported += not existed
        except (OSError, ValueError, TypeError, AttributeError):
            invalid += 1
    return {"imported": imported, "invalid": invalid}


def media_files(store, note):
    base = local_path(store, note)
    if not base.is_dir():
        return [], None, None
    images = sorted([p for p in base.glob("*") if p.is_file() and not p.is_symlink() and p.suffix.lower() in IMAGE_EXTS], key=natural_key)
    if note.kind == "视频":
        images = sorted(images, key=lambda p: not p.stem.startswith("cover"))
    video = base / "video_files/video.mp4"
    return images, video if video.is_file() else None, images[0] if images else None


def serialize_note(db, store, note, detail=False):
    images, video, cover = media_files(store, note)
    base = Path(note.path)

    def url(path):
        return f"/api/media/{note.id}/{quote(str(path.relative_to(base)), safe='/')}" if path else None

    folders = list(db.scalars(select(NoteFolder.folder_id).where(NoteFolder.note_id == note.id)))
    tags = list(db.scalars(select(NoteTag.name).where(NoteTag.note_id == note.id)))
    data = note.data
    result = {"id": note.id, "title": note.title, "author": note.author, "kind": note.kind,
              "cover": url(cover), "original_tags": data.get("tags", []), "tags": tags, "folder_ids": folders,
              "has_ocr": bool(note.ocr_text), "created_at": note.created_at, "updated_at": note.updated_at,
              "trashed_at": note.trashed_at, "liked_count": data.get("liked_count", 0), "image_count": len(images),
              "media_missing": not bool(images) or (note.kind == "视频" and not video)}
    if detail:
        result.update({"data": data, "images": [url(p) for p in images], "video": url(video), "ocr_text": note.ocr_text,
                       "files": [{"name": str(p.relative_to(base)), "url": url(p)} for p in sorted(base.rglob("*"))
                                 if p.is_file() and not p.is_symlink() and not p.name.startswith(".") and not p.name.endswith(".part")]})
    return result

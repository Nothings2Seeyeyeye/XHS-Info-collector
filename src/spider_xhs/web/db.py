from __future__ import annotations

import hashlib
import os
import time
import uuid
from contextlib import contextmanager
from pathlib import Path

from cryptography.fernet import Fernet
from dotenv import load_dotenv
from sqlalchemy import JSON, Boolean, Float, ForeignKey, Integer, String, Text, UniqueConstraint, create_engine, event, select
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, sessionmaker

from spider_xhs.paths import REPO_ROOT


def uid():
    return uuid.uuid4().hex


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(primary_key=True)
    username: Mapped[str] = mapped_column(String(80), unique=True)
    password_hash: Mapped[str] = mapped_column(Text)


class LoginSession(Base):
    __tablename__ = "sessions"
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    expires_at: Mapped[float] = mapped_column(Float)


class Setting(Base):
    __tablename__ = "settings"
    key: Mapped[str] = mapped_column(String(80), primary_key=True)
    value: Mapped[dict] = mapped_column(JSON)


class Note(Base):
    __tablename__ = "notes"
    id: Mapped[str] = mapped_column(String(128), primary_key=True)
    title: Mapped[str] = mapped_column(Text, default="无标题")
    author: Mapped[str] = mapped_column(Text, default="")
    kind: Mapped[str] = mapped_column(String(20), default="图集", index=True)
    data: Mapped[dict] = mapped_column(JSON, default=dict)
    path: Mapped[str] = mapped_column(Text, default="")
    search_text: Mapped[str] = mapped_column(Text, default="")
    ocr_text: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[float] = mapped_column(Float, default=time.time, index=True)
    updated_at: Mapped[float] = mapped_column(Float, default=time.time)
    trashed_at: Mapped[float | None] = mapped_column(Float, nullable=True, index=True)


class Folder(Base):
    __tablename__ = "folders"
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=uid)
    name: Mapped[str] = mapped_column(String(120))
    parent_id: Mapped[str | None] = mapped_column(ForeignKey("folders.id", ondelete="CASCADE"), nullable=True)
    created_at: Mapped[float] = mapped_column(Float, default=time.time)


class NoteFolder(Base):
    __tablename__ = "note_folders"
    note_id: Mapped[str] = mapped_column(ForeignKey("notes.id", ondelete="CASCADE"), primary_key=True)
    folder_id: Mapped[str] = mapped_column(ForeignKey("folders.id", ondelete="CASCADE"), primary_key=True)


class NoteTag(Base):
    __tablename__ = "note_tags"
    note_id: Mapped[str] = mapped_column(ForeignKey("notes.id", ondelete="CASCADE"), primary_key=True)
    name: Mapped[str] = mapped_column(String(80), primary_key=True)


class Job(Base):
    __tablename__ = "jobs"
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=uid)
    kind: Mapped[str] = mapped_column(String(20), default="collect")
    title: Mapped[str] = mapped_column(Text)
    state: Mapped[str] = mapped_column(String(24), default="queued", index=True)
    payload: Mapped[dict] = mapped_column(JSON, default=dict)
    checkpoint: Mapped[dict] = mapped_column(JSON, default=dict)
    message: Mapped[str] = mapped_column(Text, default="等待执行")
    created_at: Mapped[float] = mapped_column(Float, default=time.time)
    updated_at: Mapped[float] = mapped_column(Float, default=time.time)


class JobItem(Base):
    __tablename__ = "job_items"
    __table_args__ = (UniqueConstraint("job_id", "item_key"),)
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=uid)
    job_id: Mapped[str] = mapped_column(ForeignKey("jobs.id", ondelete="CASCADE"), index=True)
    item_key: Mapped[str] = mapped_column(String(128))
    note_id: Mapped[str] = mapped_column(String(128), default="", index=True)
    url: Mapped[str] = mapped_column(Text, default="")
    state: Mapped[str] = mapped_column(String(20), default="pending")
    message: Mapped[str] = mapped_column(Text, default="")
    checkpoint: Mapped[dict] = mapped_column(JSON, default=dict)


class AIModel(Base):
    __tablename__ = "ai_models"
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=uid)
    name: Mapped[str] = mapped_column(String(100))
    base_url: Mapped[str] = mapped_column(Text)
    model: Mapped[str] = mapped_column(String(200))
    vision: Mapped[bool] = mapped_column(Boolean, default=True)
    encrypted_key: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[float] = mapped_column(Float, default=time.time)


class ChatThread(Base):
    __tablename__ = "chat_threads"
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=uid)
    title: Mapped[str] = mapped_column(String(120), default="新对话")
    source_ids: Mapped[list] = mapped_column(JSON, default=list)
    model_id: Mapped[str] = mapped_column(String(32), default="")
    created_at: Mapped[float] = mapped_column(Float, default=time.time)
    updated_at: Mapped[float] = mapped_column(Float, default=time.time, index=True)


class ChatMessage(Base):
    __tablename__ = "chat_messages"
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=uid)
    thread_id: Mapped[str] = mapped_column(ForeignKey("chat_threads.id", ondelete="CASCADE"), index=True)
    role: Mapped[str] = mapped_column(String(12))
    content: Mapped[str] = mapped_column(Text, default="")
    context: Mapped[str] = mapped_column(Text, default="")
    sources: Mapped[list] = mapped_column(JSON, default=list)
    status: Mapped[str] = mapped_column(String(20), default="completed")
    error: Mapped[str] = mapped_column(Text, default="")
    model_name: Mapped[str] = mapped_column(String(100), default="")
    reply_to: Mapped[str] = mapped_column(String(32), default="")
    created_at: Mapped[float] = mapped_column(Float, default=time.time, index=True)


class Store:
    def __init__(self, state_dir=None, media_root=None):
        load_dotenv(REPO_ROOT / ".env")
        self.root = Path(state_dir or os.getenv("XHS_APP_DATA") or REPO_ROOT / "datas/app").resolve()
        self.media = Path(media_root or os.getenv("XHS_MEDIA_BASE") or REPO_ROOT / "datas/media_datas").resolve()
        self.excel = Path(os.getenv("XHS_EXCEL_BASE") or REPO_ROOT / "datas/excel_datas").resolve()
        self.root.mkdir(parents=True, exist_ok=True, mode=0o700)
        self.media.mkdir(parents=True, exist_ok=True)
        self.excel.mkdir(parents=True, exist_ok=True)
        key_path = self.root / "secret.key"
        try:
            fd = os.open(key_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            with os.fdopen(fd, "wb") as f:
                f.write(Fernet.generate_key())
        except FileExistsError:
            pass
        self.cipher = Fernet(key_path.read_bytes())
        self.engine = create_engine(f"sqlite:///{self.root / 'library.sqlite3'}", connect_args={"check_same_thread": False, "timeout": 30})

        @event.listens_for(self.engine, "connect")
        def sqlite_setup(connection, _):
            connection.execute("PRAGMA foreign_keys=ON")
            connection.execute("PRAGMA journal_mode=WAL")
            connection.execute("PRAGMA busy_timeout=30000")

        Base.metadata.create_all(self.engine)
        self.Session = sessionmaker(self.engine, expire_on_commit=False)
        if self.get("schema_version") is None:
            self.put("schema_version", 1)
        if self.get("xhs_cookie") is None and os.getenv("COOKIES"):
            self.put_secret("xhs_cookie", os.environ["COOKIES"])
            self.put("xhs_status", {"state": "unverified", "nickname": "已导入本地配置"})
        if self.get("ocr") is None:
            self.put("ocr", {
                "mode": "async", "model": os.getenv("OCR_MODEL", "PaddleOCR-VL-1.6"),
                "url": os.getenv("OCR_ASYNC_JOB_URL", "https://paddleocr.aistudio-app.com/api/v2/ocr/jobs"),
                "sync_url": os.getenv("OCR_SYNC_URL", "https://o6f4pfe0wf57ico6.aistudio-app.com/layout-parsing"),
            })
            if os.getenv("OCR_TOKEN"):
                self.put_secret("ocr_key", os.environ["OCR_TOKEN"])

    @contextmanager
    def session(self):
        with self.Session() as db:
            try:
                yield db
                db.commit()
            except BaseException:
                db.rollback()
                raise

    def get(self, key, default=None):
        with self.session() as db:
            row = db.get(Setting, key)
            return row.value if row else default

    def put(self, key, value):
        with self.session() as db:
            db.merge(Setting(key=key, value=value))

    def put_secret(self, key, value):
        self.put(key, self.cipher.encrypt(value.encode()).decode())

    def secret(self, key):
        value = self.get(key)
        return self.cipher.decrypt(value.encode()).decode() if value else ""

    def close(self):
        self.engine.dispose()


def token_hash(value):
    return hashlib.sha256(value.encode()).hexdigest()

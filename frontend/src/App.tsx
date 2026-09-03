import {
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
  type FormEvent,
  type ReactNode,
} from "react";
import {
  DndContext,
  DragOverlay,
  KeyboardSensor,
  PointerSensor,
  useDraggable,
  useDroppable,
  useSensor,
  useSensors,
  type DragEndEvent,
} from "@dnd-kit/core";
import { CSS } from "@dnd-kit/utilities";
import {
  ArrowDownToLine,
  ArrowLeft,
  ArrowRight,
  ArrowUpRight,
  BookOpen,
  Check,
  CheckCheck,
  CheckCircle2,
  ChevronDown,
  ChevronLeft,
  ChevronRight,
  CircleHelp,
  Clock3,
  Download,
  Eye,
  Ellipsis,
  ExternalLink,
  FileText,
  Film,
  Folder as FolderIcon,
  FolderOpen,
  FolderPlus,
  GripVertical,
  Heart,
  Image as ImageIcon,
  Inbox,
  Layers3,
  LayoutGrid,
  List,
  Link2,
  ListFilter,
  LoaderCircle,
  LogOut,
  MessageCircle,
  Pause,
  Play,
  Plus,
  QrCode,
  RefreshCw,
  ScanText,
  Search,
  Settings2,
  ShieldCheck,
  Sparkles,
  Star,
  Tags,
  Trash2,
  ZoomIn,
  Command,
  CheckSquare,
  X,
  XCircle,
} from "lucide-react";
import { Button } from "./components/ui/button";
import { Dialog } from "./components/ui/dialog";
import { TagFilter } from "./components/TagFilter";
import {
  api,
  compact,
  date,
  safeLink,
  states,
  type Folder,
  type Job,
  type Note,
  type NoteDetail,
  type Overview,
} from "./api";

const emptyOverview: Overview = {
  total: 0,
  images: 0,
  videos: 0,
  ocr: 0,
  trash: 0,
  folders: [],
  tags: [],
  original_tags: [],
  xhs: { state: "missing" },
  running_jobs: 0,
};
type Notice = (text: string, error?: boolean) => void;
type View = "library" | "capture" | "tasks" | "trash" | "settings";
const icons = {
  library: Layers3,
  capture: Link2,
  tasks: Clock3,
  trash: Trash2,
  settings: Settings2,
};

function Busy({ text = "正在加载…" }: { text?: string }) {
  return (
    <div className="busy">
      <LoaderCircle className="spin" size={20} />
      <span>{text}</span>
    </div>
  );
}
function Empty({
  icon: Icon = Inbox,
  title,
  description,
  children,
}: {
  icon?: typeof Inbox;
  title: string;
  description: string;
  children?: ReactNode;
}) {
  return (
    <div className="empty">
      <span className="empty-icon">
        <Icon size={29} />
      </span>
      <h2>{title}</h2>
      <p>{description}</p>
      {children}
    </div>
  );
}
function Brand() {
  return (
    <div className="brand">
      <span className="brand-mark">
        <BookOpen size={23} />
      </span>
      <div>
        <strong>
          拾页<span className="brand-dot">/</span>
        </strong>
        <small>THE PRIVATE ARCHIVE</small>
      </div>
    </div>
  );
}

function Auth({
  initialized,
  done,
}: {
  initialized: boolean;
  done: () => void;
}) {
  const [username, setUsername] = useState(""),
    [password, setPassword] = useState(""),
    [confirm, setConfirm] = useState(""),
    [remember, setRemember] = useState(true);
  const [busy, setBusy] = useState(false),
    [error, setError] = useState("");
  async function submit(e: FormEvent) {
    e.preventDefault();
    setError("");
    if (!initialized && password !== confirm)
      return setError("两次输入的密码不一致");
    setBusy(true);
    try {
      await api(initialized ? "/auth/login" : "/auth/setup", {
        username,
        password,
        remember,
      });
      done();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }
  return (
    <main className="auth-page">
      <section className="auth-story">
        <Brand />
        <div className="auth-editorial">
          <span className="eyebrow">YOUR LOCAL INSPIRATION LIBRARY</span>
          <h1>
            灵感不必散落，
            <br />
            把喜欢的，<em>留下来。</em>
          </h1>
          <p>
            收藏图文与影像，整理思考与线索。
            <br />
            在自己的电脑上，慢慢积累一座素材库。
          </p>
          <div className="auth-art" aria-hidden="true">
            <div className="paper p-one">
              <ImageIcon size={28} />
              <i />
              <i />
              <span>观察 · 记录 · 再发现</span>
            </div>
            <div className="paper p-two">
              <span>灵感档案</span>
              <b>
                01
                <br />
                <em>Collect.</em>
              </b>
              <span>YOUR IDEAS, WELL KEPT.</span>
            </div>
          </div>
        </div>
        <span className="local-foot">
          <span className="status-dot" /> 本地存储 · 由你掌握
        </span>
      </section>
      <section className="auth-form">
        <div className="auth-form-inner">
          <span className="eyebrow">
            {initialized ? "WELCOME BACK" : "MAKE IT YOURS"}
          </span>
          <h2>{initialized ? "回到你的素材库" : "建立你的工作台"}</h2>
          <p>
            {initialized
              ? "登录本地账号，继续整理你的灵感。"
              : "首次使用，创建一个属于你的管理员账号。"}
          </p>
          <form onSubmit={submit}>
            <label>
              用户名
              <input
                autoComplete="username"
                required
                maxLength={80}
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                placeholder="你的名字"
                autoFocus
              />
            </label>
            <label>
              密码
              <input
                type="password"
                minLength={8}
                maxLength={256}
                autoComplete={initialized ? "current-password" : "new-password"}
                required
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder="至少 8 个字符"
              />
            </label>
            {!initialized && (
              <label>
                确认密码
                <input
                  type="password"
                  minLength={8}
                  autoComplete="new-password"
                  required
                  value={confirm}
                  onChange={(e) => setConfirm(e.target.value)}
                  placeholder="再输入一次密码"
                />
              </label>
            )}
            <label className="checkbox-label">
              <input
                type="checkbox"
                checked={remember}
                onChange={(e) => setRemember(e.target.checked)}
              />
              记住登录状态
            </label>
            {error && (
              <p className="error-box" role="alert">
                {error}
              </p>
            )}
            <Button type="submit" disabled={busy} className="auth-submit">
              {busy ? (
                <LoaderCircle className="spin" size={18} />
              ) : (
                <ArrowRight size={18} />
              )}{" "}
              {initialized ? "进入素材库" : "创建工作台"}
            </Button>
          </form>
          <p className="auth-note">
            <ShieldCheck size={16} />
            这是本地工作台账号，小红书账号将在登录后连接。
          </p>
        </div>
      </section>
    </main>
  );
}

function FolderRow({
  folder,
  folders,
  active,
  select,
  edit,
  depth = 0,
}: {
  folder: Folder;
  folders: Folder[];
  active: string;
  select: (id: string) => void;
  edit: (f: Folder) => void;
  depth?: number;
}) {
  const [expanded, setExpanded] = useState(true);
  const draggable = useDraggable({
    id: `folder:${folder.id}`,
    data: { type: "folder", id: folder.id, label: folder.name },
  });
  const drop = useDroppable({
    id: `drop:${folder.id}`,
    data: { folder: folder.id },
  });
  const children = folders.filter((f) => f.parent_id === folder.id);
  return (
    <div>
      <div
        ref={(node) => {
          draggable.setNodeRef(node);
          drop.setNodeRef(node);
        }}
        style={{
          paddingLeft: 10 + depth * 15,
          opacity: draggable.isDragging ? 0.4 : 1,
        }}
        className={`folder-row ${active === folder.id ? "active" : ""} ${drop.isOver ? "drop-over" : ""}`}
      >
        <button
          className="folder-toggle"
          aria-label={`${expanded ? "收起" : "展开"}${folder.name}`}
          onClick={() => setExpanded(!expanded)}
        >
          {children.length ? (
            expanded ? (
              <ChevronDown size={13} />
            ) : (
              <ChevronRight size={13} />
            )
          ) : (
            <span />
          )}
        </button>
        <button className="folder-label" onClick={() => select(folder.id)}>
          <FolderIcon size={16} />
          <span>{folder.name}</span>
          <small>{folder.count}</small>
        </button>
        <button
          className="folder-grip"
          aria-label={`拖动文件夹 ${folder.name}`}
          {...draggable.listeners}
          {...draggable.attributes}
        >
          <GripVertical size={14} />
        </button>
        <button
          className="folder-more"
          aria-label={`管理文件夹 ${folder.name}`}
          onClick={() => edit(folder)}
        >
          <Ellipsis size={16} />
        </button>
      </div>
      {expanded &&
        children.map((f) => (
          <FolderRow
            key={f.id}
            folder={f}
            folders={folders}
            active={active}
            select={select}
            edit={edit}
            depth={depth + 1}
          />
        ))}
    </div>
  );
}
function RootDrop({ children }: { children: ReactNode }) {
  const { setNodeRef, isOver } = useDroppable({ id: "drop:root" });
  return (
    <div
      ref={setNodeRef}
      className={isOver ? "root-drop drop-over" : "root-drop"}
    >
      {children}
    </div>
  );
}

function NoteCard({
  note,
  selected,
  selection,
  toggle,
  open,
  index = 0,
}: {
  note: Note;
  selected: boolean;
  selection: string[];
  toggle: () => void;
  open: () => void;
  index?: number;
}) {
  const { attributes, listeners, setNodeRef, transform, isDragging } =
    useDraggable({
      id: `note:${note.id}`,
      data: {
        type: "note",
        ids: selected ? selection : [note.id],
        label: note.title,
      },
    });
  return (
    <article
      className={`note-card ${selected ? "selected" : ""}`}
      ref={setNodeRef}
      style={{
        transform: CSS.Translate.toString(transform),
        opacity: isDragging ? 0.35 : 1,
        animationDelay: `${Math.min(index, 10) * 25}ms`,
      }}
    >
      <div className="note-cover">
        <button
          className="cover-button"
          onClick={open}
          aria-label={`查看笔记：${note.title}`}
        >
          {note.cover ? (
            <img loading="lazy" src={note.cover} alt={note.title} />
          ) : (
            <span className="missing-cover">
              <ImageIcon size={32} />
              <small>暂无本地封面</small>
            </span>
          )}
        </button>
        <label
          className={`card-check ${selected ? "checked" : ""}`}
          title="选择笔记"
        >
          <input
            aria-label={`选择 ${note.title}`}
            type="checkbox"
            checked={selected}
            onChange={toggle}
          />
          <span>{selected && <Check size={14} />}</span>
        </label>
        <button
          className="card-drag"
          aria-label={`拖动笔记 ${note.title}`}
          {...listeners}
          {...attributes}
        >
          <GripVertical size={16} />
        </button>
        <span className="media-badge">
          {note.kind === "视频" ? (
            <>
              <Play size={12} fill="currentColor" />
              视频
            </>
          ) : (
            <>
              <ImageIcon size={12} />
              {note.image_count} 图
            </>
          )}
        </span>
        {note.has_ocr && (
          <span className="ocr-badge" title="已识别图片文字">
            <ScanText size={12} />
          </span>
        )}
      </div>
      <div className="note-card-body">
        <div className="card-eyebrow">
          <span>
            {note.kind === "视频" ? "MOTION" : "STILL"} /{" "}
            {String(index + 1).padStart(2, "0")}
          </span>
          <span>{date(note.created_at)}</span>
        </div>
        <button className="note-title" onClick={open}>
          {note.title}
        </button>
        <div className="note-author">
          <span className="mini-avatar">{note.author.slice(0, 1)}</span>
          <span>{note.author}</span>
          <small>
            <Heart size={12} />
            {compact(note.liked_count)}
          </small>
        </div>
        <div className="card-tags">
          {[...note.tags, ...note.original_tags].slice(0, 2).map((tag, i) => (
            <span key={i}>
              {note.tags.includes(tag) ? "" : "#"}
              {tag}
            </span>
          ))}
          {!note.tags.length && !note.original_tags.length && (
            <span className="muted">{date(note.created_at)} 收录</span>
          )}
        </div>
        <button
          className="card-open"
          onClick={open}
          aria-label={`预览 ${note.title}`}
        >
          <Eye size={15} />
          <span>查看详情</span>
          <ArrowUpRight size={15} />
        </button>
      </div>
    </article>
  );
}

function QRDialog({
  open,
  close,
  connected,
  notify,
}: {
  open: boolean;
  close: () => void;
  connected: () => void;
  notify: Notice;
}) {
  const [qr, setQR] = useState<{ id: string; image: string } | null>(null),
    [message, setMessage] = useState(""),
    [state, setState] = useState("loading"),
    [generation, setGeneration] = useState(0);
  useEffect(() => {
    if (!open) return;
    let active = true;
    setState("loading");
    setQR(null);
    setMessage("正在生成登录二维码…");
    api<{ id: string; image: string }>("/xhs/qrcode", {})
      .then((data) => {
        if (active) {
          setQR(data);
          setState("waiting");
          setMessage("使用小红书 App 扫码，并在手机上确认登录");
        }
      })
      .catch((e) => {
        if (active) {
          setState("error");
          setMessage(e.message);
        }
      });
    return () => {
      active = false;
    };
  }, [open, generation]);
  useEffect(() => {
    if (!open || !qr || !["waiting", "verifying"].includes(state)) return;
    let active = true,
      failures = 0,
      timer: ReturnType<typeof setTimeout>;
    async function poll() {
      try {
        const result = await api<{ state: string; message: string }>(
          `/xhs/qrcode/${qr!.id}`,
        );
        if (!active) return;
        failures = 0;
        setMessage(result.message);
        if (result.state === "success") {
          setState("success");
          connected();
          notify(result.message);
          return;
        }
        if (result.state === "verifying") {
          setState("verifying");
        }
        if (result.state === "expired") {
          setState("expired");
          return;
        }
        if (result.state === "blocked" || result.state === "error") {
          setState("error");
          setQR(null);
          return;
        }
      } catch (e) {
        if (active) {
          setMessage((e as Error).message);
          failures += 1;
          if (failures >= 3) {
            setState("error");
            setQR(null);
            return;
          }
        }
      }
      if (active) timer = setTimeout(poll, 2500);
    }
    timer = setTimeout(poll, 1500);
    return () => {
      active = false;
      clearTimeout(timer);
    };
  }, [open, qr, state, connected, notify]);
  return (
    <Dialog
      open={open}
      onOpenChange={(v) => !v && close()}
      title="连接小红书账号"
      description="扫码登录后，工作台会自动保存凭据并继续采集。"
    >
      <div className="qr-box">
        {state === "loading" ? (
          <Busy text="准备二维码" />
        ) : state === "verifying" ? (
          <Busy text="正在校验小红书账号…" />
        ) : qr ? (
          <img src={qr.image} alt="小红书登录二维码" />
        ) : (
          <QrCode size={75} />
        )}
      </div>
      <p className="qr-message" role="status">
        {message}
      </p>
      <div className="dialog-actions">
        {(state === "error" || state === "expired") && (
          <Button variant="ghost" asChild>
            <a
              href="https://www.xiaohongshu.com"
              target="_blank"
              rel="noreferrer"
            >
              <ExternalLink size={16} />
              打开小红书官网
            </a>
          </Button>
        )}
        <Button
          variant="secondary"
          disabled={state === "loading"}
          onClick={() => setGeneration((g) => g + 1)}
        >
          <RefreshCw size={16} />
          重新生成
        </Button>
      </div>
    </Dialog>
  );
}

function ExportDialog({
  ids,
  folder,
  close,
  notify,
}: {
  ids: string[] | null;
  folder?: string;
  close: () => void;
  notify: Notice;
}) {
  const [format, setFormat] = useState("all"),
    [busy, setBusy] = useState(false);
  async function run() {
    setBusy(true);
    try {
      const result = await api<{ url: string; name: string }>("/exports", {
        note_ids: ids || [],
        folder_id: folder || null,
        format,
      });
      const a = document.createElement("a");
      a.href = result.url;
      a.download = result.name;
      document.body.appendChild(a);
      a.click();
      a.remove();
      notify("导出文件已准备好");
      close();
    } catch (e) {
      notify((e as Error).message, true);
    } finally {
      setBusy(false);
    }
  }
  return (
    <Dialog
      open={ids !== null}
      onOpenChange={(v) => !v && !busy && close()}
      title="导出素材"
      description={
        folder
          ? "导出这个文件夹及子文件夹中的全部笔记。"
          : `已选择 ${ids?.length || 0} 条笔记。`
      }
    >
      <div className="export-options">
        {[
          ["all", "完整资料", "媒体、TXT / JSON、OCR 结果及 Excel 汇总"],
          [
            "context",
            "文字与结构化数据",
            "TXT、JSON 和已有 OCR Markdown 同时导出",
          ],
          ["media-image", "图片文件", "原图与 PNG 副本"],
          ["media-video", "视频与音频", "MP4 及已提取的 MP3 / WAV"],
          ["excel", "Excel 表格", "笔记信息与互动数据"],
        ].map(([value, title, sub]) => (
          <label
            className={`export-option ${format === value ? "active" : ""}`}
            key={value}
          >
            <input
              type="radio"
              name="format"
              value={value}
              checked={format === value}
              onChange={() => setFormat(value)}
            />
            <span>
              <strong>{title}</strong>
              <small>{sub}</small>
            </span>
          </label>
        ))}
      </div>
      <p className="help-text">
        沿用已有文件格式，多文件会打包为 ZIP 方便下载。
      </p>
      <div className="dialog-actions">
        <Button variant="secondary" onClick={close} disabled={busy}>
          取消
        </Button>
        <Button onClick={run} disabled={busy}>
          {busy ? (
            <LoaderCircle size={16} className="spin" />
          ) : (
            <Download size={16} />
          )}{" "}
          {busy ? "正在整理文件" : "导出"}
        </Button>
      </div>
    </Dialog>
  );
}

function NoteModal({
  id,
  close,
  overview,
  refresh,
  notify,
  exportNotes,
  organize,
}: {
  id: string | null;
  close: () => void;
  overview: Overview;
  refresh: number;
  notify: Notice;
  exportNotes: (ids: string[]) => void;
  organize: (action: string, ids: string[]) => void;
}) {
  const [note, setNote] = useState<NoteDetail | null>(null),
    [error, setError] = useState(""),
    [index, setIndex] = useState(0),
    [tab, setTab] = useState("content"),
    [lightbox, setLightbox] = useState(false);
  useEffect(() => {
    if (!id) return;
    let active = true;
    setError("");
    api<NoteDetail>(`/notes/${id}`)
      .then((n) => {
        if (active) setNote(n);
      })
      .catch((e) => {
        if (active) setError(e.message);
      });
    return () => {
      active = false;
    };
  }, [id, refresh]);
  useEffect(() => {
    setNote(null);
    setIndex(0);
    setTab("content");
    setLightbox(false);
  }, [id]);
  useEffect(() => {
    if (!id || !note || note.kind === "视频" || note.images.length < 2) return;
    const onKey = (event: KeyboardEvent) => {
      if (
        event.target instanceof HTMLElement &&
        event.target.closest(
          "input, textarea, select, [contenteditable=true], [role=tablist]",
        )
      )
        return;
      if (
        document.querySelectorAll('[role="dialog"]').length > (lightbox ? 2 : 1)
      )
        return;
      if (event.key === "ArrowLeft" || event.key === "ArrowRight") {
        event.preventDefault();
        setIndex(
          (i) =>
            (i + (event.key === "ArrowLeft" ? -1 : 1) + note.images.length) %
            note.images.length,
        );
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [id, note, lightbox]);
  async function runOCR() {
    try {
      await api("/jobs", { kind: "ocr", note_ids: [id] });
      notify("已加入文字识别任务，可在任务页查看进度");
    } catch (e) {
      notify((e as Error).message, true);
    }
  }
  return (
    <>
      <Dialog
        open={!!id}
        onOpenChange={(v) => !v && close()}
        title={note?.title || "笔记详情"}
        wide
      >
        {error ? (
          <Empty title="暂时无法打开" description={error} />
        ) : !note ? (
          <Busy />
        ) : (
          <div className="note-detail">
            <section className="detail-media">
              {note.kind === "视频" && note.video ? (
                <video
                  key={note.id}
                  src={note.video}
                  poster={note.cover || undefined}
                  controls
                  preload="metadata"
                />
              ) : note.images.length ? (
                <img
                  className="detail-image"
                  src={note.images[Math.min(index, note.images.length - 1)]}
                  alt={`${note.title} 第 ${index + 1} 张图片`}
                  onDoubleClick={() => setLightbox(true)}
                />
              ) : (
                <Empty
                  title="媒体尚未下载"
                  description="可在任务页补齐失败的下载。"
                />
              )}
              {note.kind !== "视频" && note.images.length > 0 && (
                <button
                  className="viewer-zoom"
                  onClick={() => setLightbox(true)}
                  aria-label="放大查看图片"
                >
                  <ZoomIn size={17} />
                  <span>查看原图</span>
                </button>
              )}
              {note.kind !== "视频" && note.images.length > 1 && (
                <>
                  <button
                    className="media-arrow prev"
                    aria-label="上一张图片"
                    onClick={() =>
                      setIndex(
                        (i) =>
                          (i - 1 + note.images.length) % note.images.length,
                      )
                    }
                  >
                    <ChevronLeft size={22} />
                  </button>
                  <button
                    className="media-arrow next"
                    aria-label="下一张图片"
                    onClick={() =>
                      setIndex((i) => (i + 1) % note.images.length)
                    }
                  >
                    <ChevronRight size={22} />
                  </button>
                  <div className="image-counter">
                    {index + 1} / {note.images.length}
                  </div>
                  <div className="image-thumbs">
                    {note.images.map((src, i) => (
                      <button
                        key={src}
                        onClick={() => setIndex(i)}
                        className={i === index ? "active" : ""}
                        aria-label={`查看第 ${i + 1} 张图片`}
                      >
                        <img src={src} alt="" />
                      </button>
                    ))}
                  </div>
                </>
              )}
            </section>
            <section className="detail-content">
              <header className="detail-author">
                <span className="author-avatar">
                  {note.author.slice(0, 1)}
                  {safeLink(note.data.avatar) && (
                    <img
                      src={safeLink(note.data.avatar)}
                      alt=""
                      referrerPolicy="no-referrer"
                      onError={(e) => {
                        e.currentTarget.style.display = "none";
                      }}
                    />
                  )}
                </span>
                <div>
                  <strong>{note.author}</strong>
                  <small>
                    小红书 · {note.kind === "图集" ? "图文笔记" : "视频笔记"}
                  </small>
                </div>
                <a
                  className="origin-link"
                  href={safeLink(note.data.note_url)}
                  target="_blank"
                  rel="noreferrer"
                  title="打开原笔记"
                >
                  <ExternalLink size={17} />
                  <span>原文</span>
                </a>
              </header>
              <div className="detail-tabs" role="tablist" aria-label="笔记内容">
                {[
                  ["content", "笔记正文"],
                  ["ocr", "图片文字"],
                  ["files", "本地文件"],
                ].map(([value, name]) => (
                  <button
                    role="tab"
                    id={`note-tab-${value}`}
                    aria-controls={`note-panel-${value}`}
                    aria-selected={tab === value}
                    tabIndex={tab === value ? 0 : -1}
                    key={value}
                    className={tab === value ? "active" : ""}
                    onClick={() => setTab(value)}
                    onKeyDown={(event) => {
                      if (
                        event.key !== "ArrowLeft" &&
                        event.key !== "ArrowRight"
                      )
                        return;
                      event.preventDefault();
                      event.stopPropagation();
                      const keys = ["content", "ocr", "files"];
                      const next =
                        keys[
                          (keys.indexOf(value) +
                            (event.key === "ArrowRight" ? 1 : 2)) %
                            3
                        ];
                      setTab(next);
                      document.getElementById(`note-tab-${next}`)?.focus();
                    }}
                  >
                    {name}
                    {value === "ocr" && note.has_ocr && (
                      <span className="tiny-dot" />
                    )}
                  </button>
                ))}
              </div>
              <div
                className="detail-scroll"
                role="tabpanel"
                id={`note-panel-${tab}`}
                aria-labelledby={`note-tab-${tab}`}
              >
                {tab === "content" && (
                  <>
                    <h2>{note.title}</h2>
                    <p className="note-description">
                      {String(note.data.desc || "")}
                    </p>
                    <div className="original-tags">
                      {note.original_tags.map((t) => (
                        <span key={t}>#{t}</span>
                      ))}
                    </div>
                    <p className="note-date">
                      {String(note.data.upload_time || "")}{" "}
                      {String(note.data.ip_location || "")}
                    </p>
                    <div className="detail-organize">
                      <span className="section-label">我的整理</span>
                      <div className="personal-tags">
                        {note.tags.map((t) => (
                          <span key={t}>
                            <Tags size={12} />
                            {t}
                          </span>
                        ))}
                        {note.folder_ids.map((f) => (
                          <span key={f}>
                            <FolderIcon size={12} />
                            {overview.folders.find((v) => v.id === f)?.name ||
                              "文件夹"}
                          </span>
                        ))}
                        {!note.tags.length && !note.folder_ids.length && (
                          <small>给这份灵感添加标签，或放进文件夹。</small>
                        )}
                      </div>
                    </div>
                  </>
                )}
                {tab === "ocr" &&
                  (note.has_ocr ? (
                    <>
                      <div className="ocr-status">
                        <CheckCircle2 size={15} />
                        已保存识别文字
                      </div>
                      <p className="ocr-text">{note.ocr_text}</p>
                    </>
                  ) : (
                    <Empty
                      icon={ScanText}
                      title="提取图片里的文字"
                      description="使用设置中配置的在线 OCR 服务，识别结果将保存在本地。"
                    >
                      <Button onClick={runOCR}>
                        <ScanText size={16} />
                        开始识别
                      </Button>
                    </Empty>
                  ))}
                {tab === "files" && (
                  <div className="file-list">
                    {note.files.map((f) => (
                      <a href={f.url} key={f.name} download>
                        <FileText size={17} />
                        <span>{f.name}</span>
                        <ArrowDownToLine size={15} />
                      </a>
                    ))}
                  </div>
                )}
              </div>
              <div className="detail-bottom">
                <div className="note-metrics">
                  <span>
                    <Heart size={17} />
                    {compact(note.liked_count)}
                  </span>
                  <span>
                    <Star size={17} />
                    {compact(String(note.data.collected_count || 0))}
                  </span>
                  <span>
                    <MessageCircle size={17} />
                    {compact(String(note.data.comment_count || 0))}
                  </span>
                  <small>采集时的数据</small>
                </div>
                <div className="detail-actions">
                  <Button
                    variant="secondary"
                    size="sm"
                    onClick={() => organize("add_folder", [note.id])}
                  >
                    <FolderPlus size={16} />
                    归类
                  </Button>
                  <Button
                    variant="secondary"
                    size="sm"
                    onClick={() => organize("add_tag", [note.id])}
                  >
                    <Tags size={16} />
                    标签
                  </Button>
                  <Button variant="secondary" size="sm" onClick={runOCR}>
                    <ScanText size={16} />
                    OCR
                  </Button>
                  <Button size="sm" onClick={() => exportNotes([note.id])}>
                    <Download size={16} />
                    导出
                  </Button>
                </div>
              </div>
            </section>
          </div>
        )}
      </Dialog>
      <Dialog
        open={lightbox && !!note}
        onOpenChange={setLightbox}
        title="原图预览"
        className="lightbox-dialog"
        wide
      >
        {note && (
          <div className="lightbox-view">
            <header>
              <span>{note.title}</span>
              <span>
                {index + 1} / {note.images.length}
              </span>
            </header>
            <img
              src={note.images[Math.min(index, note.images.length - 1)]}
              alt={`${note.title} 原图`}
            />
            <footer>
              <Button
                variant="secondary"
                disabled={note.images.length < 2}
                onClick={() =>
                  setIndex(
                    (i) => (i - 1 + note.images.length) % note.images.length,
                  )
                }
                aria-label="原图上一张"
              >
                <ChevronLeft size={18} />
              </Button>
              <a
                href={note.images[index]}
                download
                className="btn btn-secondary"
              >
                <Download size={16} />
                下载原图
              </a>
              <Button
                variant="secondary"
                disabled={note.images.length < 2}
                onClick={() => setIndex((i) => (i + 1) % note.images.length)}
                aria-label="原图下一张"
              >
                <ChevronRight size={18} />
              </Button>
            </footer>
          </div>
        )}
      </Dialog>
    </>
  );
}

function Capture({
  notify,
  refresh,
  openJob,
}: {
  notify: Notice;
  refresh: () => void;
  openJob: (id: string) => void;
}) {
  const [input, setInput] = useState(""),
    [mode, setMode] = useState("auto"),
    [limit, setLimit] = useState(20),
    [save, setSave] = useState("all"),
    [busy, setBusy] = useState(false);
  async function submit(e: FormEvent) {
    e.preventDefault();
    setBusy(true);
    try {
      const result = await api<{ id: string }>("/jobs", {
        input,
        mode,
        limit,
        save_choice: save,
      });
      notify("采集任务已创建");
      refresh();
      openJob(result.id);
    } catch (e) {
      notify((e as Error).message, true);
    } finally {
      setBusy(false);
    }
  }
  return (
    <div className="capture-layout">
      <form className="capture-form" onSubmit={submit}>
        <div className="form-section-heading">
          <span className="soft-icon">
            <Link2 size={22} />
          </span>
          <div>
            <h2>把值得留下的，放进来</h2>
            <p>支持笔记、作者主页、收藏页，以及小红书分享文案。</p>
          </div>
        </div>
        <label>
          采集方式
          <select value={mode} onChange={(e) => setMode(e.target.value)}>
            <option value="auto">自动识别链接</option>
            <option value="single">单条 / 批量笔记</option>
            <option value="user">作者发布的笔记</option>
            <option value="collect">用户收藏的笔记</option>
            <option value="search">按关键词搜索</option>
          </select>
        </label>
        <label>
          {mode === "search" ? "搜索关键词" : "链接或分享内容"}
          <textarea
            required
            value={input}
            onChange={(e) => setInput(e.target.value)}
            rows={6}
            placeholder={
              mode === "search"
                ? "例如：露营收纳"
                : "粘贴小红书链接或分享文案…\n多个链接可以分行粘贴。"
            }
          />
        </label>
        <div className="form-two">
          <label>
            每个来源最多采集
            <input
              type="number"
              min={0}
              max={10000}
              value={limit}
              onChange={(e) => setLimit(Number(e.target.value))}
            />
            <small>0 表示不限；已入库笔记自动去重。</small>
          </label>
          <label>
            保存内容
            <select value={save} onChange={(e) => setSave(e.target.value)}>
              <option value="all">媒体与完整信息 + Excel</option>
              <option value="media">媒体与笔记信息</option>
              <option value="media-image">仅下载图文媒体</option>
              <option value="media-video">仅下载视频媒体</option>
              <option value="excel">仅笔记信息与 Excel</option>
            </select>
          </label>
        </div>
        <div className="capture-submit">
          <span>
            <ShieldCheck size={15} />
            素材保存到本机
          </span>
          <Button disabled={busy} type="submit">
            {busy ? (
              <LoaderCircle className="spin" size={17} />
            ) : (
              <Plus size={17} />
            )}
            创建采集任务
          </Button>
        </div>
      </form>
      <aside className="capture-guide">
        <span className="eyebrow">A LITTLE GUIDE</span>
        <h2>
          从一次发现，
          <br />
          到下一次创作。
        </h2>
        {[
          [
            "01",
            "粘贴链接",
            "单条笔记、作者主页和可见的收藏列表，都可以从这里开始。",
          ],
          ["02", "自动采集入库", "已完成的笔记会逐条出现，可直接点开查看。"],
          [
            "03",
            "让素材井井有条",
            "打标签、拖入文件夹，再按需识别图片文字和导出。",
          ],
        ].map(([n, title, text]) => (
          <div className="guide-step" key={n}>
            <span>{n}</span>
            <div>
              <h3>{title}</h3>
              <p>{text}</p>
            </div>
          </div>
        ))}
        <div className="guide-tip">
          <CircleHelp size={17} />
          <p>收藏需对当前账号可见。登录失效后，扫码即可继续未完成的任务。</p>
        </div>
      </aside>
    </div>
  );
}

function Settings({
  overview,
  notify,
  connect,
  refresh,
}: {
  overview: Overview;
  notify: Notice;
  connect: () => void;
  refresh: () => void;
}) {
  const [form, setForm] = useState({
      mode: "async",
      model: "PaddleOCR-VL-1.6",
      url: "",
      sync_url: "",
      key: "",
      has_key: false,
    }),
    [busy, setBusy] = useState(""),
    [loaded, setLoaded] = useState(false),
    [test, setTest] = useState("");
  useEffect(() => {
    api<typeof form>("/settings/ocr")
      .then((v) => {
        setForm({ ...v, key: "" });
        setLoaded(true);
      })
      .catch((e) => notify(e.message, true));
  }, [notify]);
  async function save(e?: FormEvent) {
    e?.preventDefault();
    setBusy("save");
    try {
      await api("/settings/ocr", { ...form, key: form.key || null }, "PUT");
      setForm((f) => ({ ...f, has_key: f.has_key || !!f.key, key: "" }));
      notify("OCR 设置已保存");
      return true;
    } catch (e) {
      notify((e as Error).message, true);
      return false;
    } finally {
      setBusy("");
    }
  }
  async function testConnection() {
    if (!(await save())) return;
    setBusy("test");
    setTest("正在提交一张测试图片，验证识别服务…");
    try {
      const result = await api<{ ok: boolean; message: string }>(
        "/settings/ocr/test",
        {},
      );
      setTest(result.message);
      notify(result.message, !result.ok);
    } catch (e) {
      setTest((e as Error).message);
      notify((e as Error).message, true);
    } finally {
      setBusy("");
    }
  }
  const field = (name: keyof typeof form, value: string) =>
    setForm((f) => ({ ...f, [name]: value }));
  return (
    <div className="settings-stack">
      <section className="settings-card">
        <div className="settings-heading">
          <span className="soft-icon">
            <QrCode size={21} />
          </span>
          <div>
            <h2>小红书账号</h2>
            <p>采集任务共用一个账号，重新扫码后自动更新登录凭据。</p>
          </div>
          <span
            className={`status-pill ${overview.xhs.state === "valid" ? "good" : ""}`}
          >
            {overview.xhs.state === "valid"
              ? "已连接"
              : overview.xhs.state === "unverified"
                ? "待验证"
                : "需要连接"}
          </span>
        </div>
        <div className="account-setting">
          <span className="author-avatar">
            {overview.xhs.nickname?.slice(0, 1) || "小"}
          </span>
          <div>
            <strong>{overview.xhs.nickname || "尚未连接账号"}</strong>
            <p>Cookie 加密保存在本机</p>
          </div>
          <Button
            variant="secondary"
            onClick={async () => {
              setBusy("check");
              try {
                const result = await api<{ state: string }>("/xhs/check", {});
                refresh();
                notify(
                  result.state === "valid"
                    ? "登录状态有效"
                    : "登录状态需要处理，请扫码或检查网络",
                  result.state !== "valid",
                );
              } catch (e) {
                notify((e as Error).message, true);
              } finally {
                setBusy("");
              }
            }}
            disabled={!!busy}
          >
            检查状态
          </Button>
          <Button onClick={connect}>
            <QrCode size={16} />
            扫码连接
          </Button>
        </div>
      </section>
      <section className="settings-card">
        <div className="settings-heading">
          <span className="soft-icon">
            <ScanText size={21} />
          </span>
          <div>
            <h2>图片文字识别</h2>
            <p>连接兼容现有 PaddleOCR 协议的服务，按需提取图片文字。</p>
          </div>
          <span className="subtle-badge">OCR MODEL</span>
        </div>
        {!loaded ? (
          <Busy />
        ) : (
          <form onSubmit={save}>
            <div className="form-two">
              <label>
                请求方式
                <select
                  value={form.mode}
                  onChange={(e) => field("mode", e.target.value)}
                >
                  <option value="async">异步任务（推荐）</option>
                  <option value="sync">同步识别</option>
                </select>
              </label>
              <label>
                默认模型
                <input
                  list="ocr-models"
                  value={form.model}
                  onChange={(e) => field("model", e.target.value)}
                  required
                  placeholder="服务支持的模型名称"
                />
                <datalist id="ocr-models">
                  <option value="PaddleOCR-VL-1.6" />
                </datalist>
              </label>
            </div>
            <label>
              异步任务 API 地址
              <input
                type="url"
                value={form.url}
                onChange={(e) => field("url", e.target.value)}
                required
              />
            </label>
            <label>
              同步识别 API 地址
              <input
                type="url"
                value={form.sync_url}
                onChange={(e) => field("sync_url", e.target.value)}
                required
              />
            </label>
            <label>
              API Key
              <span className="label-note">
                {form.has_key ? "已配置 · 留空保留现有 Key" : "尚未配置"}
              </span>
              <input
                type="password"
                autoComplete="off"
                value={form.key}
                onChange={(e) => field("key", e.target.value)}
                placeholder={
                  form.has_key ? "••••••••••••••••" : "填写 OCR 服务的访问凭据"
                }
              />
            </label>
            <p className="help-text">
              点击 OCR
              时会将所选图片提交给这个服务。连接测试会提交一张生成的测试图片。
            </p>
            {test && (
              <p className="test-result" role="status">
                {test}
              </p>
            )}
            <div className="dialog-actions">
              <Button
                variant="secondary"
                type="button"
                disabled={!!busy}
                onClick={testConnection}
              >
                {busy === "test" && <LoaderCircle size={16} className="spin" />}
                保存并测试连接
              </Button>
              <Button type="submit" disabled={!!busy}>
                保存设置
              </Button>
            </div>
          </form>
        )}
      </section>
      <section className="settings-card">
        <div className="settings-heading">
          <span className="soft-icon">
            <FolderOpen size={21} />
          </span>
          <div>
            <h2>本地素材</h2>
            <p>沿用项目的下载目录与文件结构，已有内容可再次扫描入库。</p>
          </div>
        </div>
        <div className="storage-setting">
          <span>
            {overview.total} 条素材 · {overview.images} 条图文 ·{" "}
            {overview.videos} 条视频
          </span>
          <Button
            variant="secondary"
            disabled={!!busy}
            onClick={async () => {
              setBusy("import");
              try {
                const result = await api<{ imported: number; invalid: number }>(
                  "/import",
                  {},
                );
                refresh();
                notify(
                  `扫描完成，新导入 ${result.imported} 条${result.invalid ? `，${result.invalid} 个文件无法读取` : ""}`,
                );
              } catch (e) {
                notify((e as Error).message, true);
              } finally {
                setBusy("");
              }
            }}
          >
            <RefreshCw size={16} className={busy === "import" ? "spin" : ""} />
            重新扫描
          </Button>
        </div>
      </section>
    </div>
  );
}

export default function App() {
  const [auth, setAuth] = useState<{
      initialized: boolean;
      authenticated: boolean;
      username: string;
    } | null>(null),
    [authError, setAuthError] = useState("");
  const [overview, setOverview] = useState<Overview>(emptyOverview),
    [view, setView] = useState<View>("library"),
    [activeFolder, setActiveFolder] = useState(""),
    [jobId, setJobId] = useState("");
  const [query, setQuery] = useState(""),
    [kind, setKind] = useState(""),
    [tag, setTag] = useState(""),
    [sort, setSort] = useState("newest"),
    [page, setPage] = useState(1);
  const [notes, setNotes] = useState<Note[]>([]),
    [total, setTotal] = useState(0),
    [loading, setLoading] = useState(true),
    [loadError, setLoadError] = useState(""),
    [jobs, setJobs] = useState<Job[]>([]),
    [jobDetail, setJobDetail] = useState<Job | null>(null);
  const [selected, setSelected] = useState<string[]>([]),
    [detail, setDetail] = useState<string | null>(null),
    [revision, setRevision] = useState(0),
    [toast, setToast] = useState<{
      text: string;
      error: boolean;
      id: number;
    } | null>(null);
  const [qrOpen, setQROpen] = useState(false),
    [exportIds, setExportIds] = useState<string[] | null>(null),
    [exportFolder, setExportFolder] = useState("");
  const [folderEditor, setFolderEditor] = useState<Folder | "new" | null>(null),
    [folderName, setFolderName] = useState(""),
    [folderParent, setFolderParent] = useState("");
  const [organization, setOrganization] = useState<{
      action: string;
      ids: string[];
    } | null>(null),
    [orgValue, setOrgValue] = useState(""),
    [busy, setBusy] = useState(false),
    [confirm, setConfirm] = useState<{
      title: string;
      text: string;
      run: () => Promise<void>;
    } | null>(null);
  const [dragLabel, setDragLabel] = useState(""),
    [sidebarOpen, setSidebarOpen] = useState(false);
  const [layout, setLayout] = useState<"gallery" | "list">(() =>
    localStorage.getItem("shiyi-layout") === "list" ? "list" : "gallery",
  );
  const [selecting, setSelecting] = useState(false);
  const [focusSearch, setFocusSearch] = useState(false);
  const searchRef = useRef<HTMLInputElement>(null);
  const sidebarRef = useRef<HTMLElement>(null);
  const [taskFilter, setTaskFilter] = useState("all");
  useEffect(() => {
    const onResize = () => {
      if (window.innerWidth > 620) setSidebarOpen(false);
    };
    window.addEventListener("resize", onResize);
    return () => window.removeEventListener("resize", onResize);
  }, []);
  useEffect(() => {
    if (!sidebarOpen || window.innerWidth > 620) return;
    const previous =
      document.activeElement instanceof HTMLElement
        ? document.activeElement
        : null;
    const controls = () =>
      Array.from(
        sidebarRef.current?.querySelectorAll<HTMLElement>(
          "button:not([disabled]), a[href], input, select",
        ) || [],
      ).filter((element) => element.offsetParent !== null);
    const frame = requestAnimationFrame(() => controls()[0]?.focus());
    const trap = (event: KeyboardEvent) => {
      if (document.querySelector('[role="dialog"]')) return;
      if (event.key === "Escape") {
        event.preventDefault();
        setSidebarOpen(false);
        return;
      }
      if (event.key !== "Tab") return;
      const items = controls(),
        first = items[0],
        last = items[items.length - 1];
      if (event.shiftKey && document.activeElement === first) {
        event.preventDefault();
        last?.focus();
      }
      if (!event.shiftKey && document.activeElement === last) {
        event.preventDefault();
        first?.focus();
      }
    };
    document.addEventListener("keydown", trap);
    return () => {
      cancelAnimationFrame(frame);
      document.removeEventListener("keydown", trap);
      if (previous?.isConnected) previous.focus();
    };
  }, [sidebarOpen]);
  useEffect(() => {
    localStorage.setItem("shiyi-layout", layout);
  }, [layout]);
  useEffect(() => {
    if (focusSearch && searchRef.current) {
      const frame = requestAnimationFrame(() => {
        searchRef.current?.focus();
        setFocusSearch(false);
      });
      return () => cancelAnimationFrame(frame);
    }
  }, [focusSearch, view]);
  useEffect(() => {
    window.scrollTo({ top: 0, behavior: "auto" });
  }, [view, activeFolder, jobId, page]);
  useEffect(() => {
    const shortcut = (event: KeyboardEvent) => {
      if (
        (event.metaKey || event.ctrlKey) &&
        event.key.toLowerCase() === "k" &&
        auth?.authenticated
      ) {
        event.preventDefault();
        setView("library");
        setActiveFolder("");
        setJobId("");
        setDetail(null);
        setFocusSearch(true);
      }
    };
    window.addEventListener("keydown", shortcut);
    return () => window.removeEventListener("keydown", shortcut);
  }, [auth?.authenticated]);
  const refresh = useCallback(() => setRevision((v) => v + 1), []);
  const notify: Notice = useCallback(
    (text, error = false) => setToast({ text, error, id: Date.now() }),
    [],
  );
  const loadAuth = useCallback(() => {
    api<typeof auth>("/auth/status")
      .then(setAuth)
      .catch((e) => setAuthError(e.message));
  }, []);
  useEffect(() => {
    loadAuth();
    window.addEventListener("session-expired", loadAuth);
    return () => window.removeEventListener("session-expired", loadAuth);
  }, [loadAuth]);
  useEffect(() => {
    if (!toast) return;
    const timer = setTimeout(() => setToast(null), 5500);
    return () => clearTimeout(timer);
  }, [toast]);
  useEffect(() => {
    if (!auth?.authenticated) return;
    let active = true;
    const load = () => {
      api<Overview>("/overview")
        .then((v) => active && setOverview(v))
        .catch((e) => active && notify(e.message, true));
      api<Job[]>("/jobs")
        .then((v) => active && setJobs(v))
        .catch(() => {});
    };
    load();
    const timer = setInterval(load, 4000);
    return () => {
      active = false;
      clearInterval(timer);
    };
  }, [auth?.authenticated, revision, notify]);
  useEffect(() => {
    setPage(1);
    setSelected([]);
  }, [view, activeFolder, query, kind, tag, jobId, sort]);
  const noteQuery = useMemo(
    () =>
      new URLSearchParams({
        q: query,
        kind,
        tag: tag.startsWith("my:") ? tag.slice(3) : "",
        original_tag: tag.startsWith("raw:") ? tag.slice(4) : "",
        folder: activeFolder,
        job: jobId,
        trash: String(view === "trash"),
        page: String(page),
        sort,
      }).toString(),
    [query, kind, tag, activeFolder, jobId, view, page, sort],
  );
  useEffect(() => {
    if (!auth?.authenticated) return;
    let active = true;
    setLoading(true);
    setLoadError("");
    const load = () =>
      api<{ items: Note[]; total: number }>(`/notes?${noteQuery}`)
        .then((v) => {
          if (active) {
            setNotes(v.items);
            setTotal(v.total);
            setLoading(false);
            setLoadError("");
          }
        })
        .catch((e) => {
          if (active) {
            setLoadError(e.message);
            setLoading(false);
          }
        });
    load();
    const timer = setInterval(
      load,
      jobId || overview.running_jobs ? 2500 : 15000,
    );
    return () => {
      active = false;
      clearInterval(timer);
    };
  }, [auth?.authenticated, noteQuery, revision, !!overview.running_jobs]);
  useEffect(() => {
    if (!jobId) {
      setJobDetail(null);
      return;
    }
    let active = true;
    const load = () =>
      api<Job>(`/jobs/${jobId}`)
        .then((j) => active && setJobDetail(j))
        .catch(() => {});
    load();
    const timer = setInterval(load, 2500);
    return () => {
      active = false;
      clearInterval(timer);
    };
  }, [jobId, revision]);
  const sensors = useSensors(
    useSensor(PointerSensor, { activationConstraint: { distance: 7 } }),
    useSensor(KeyboardSensor),
  );
  const navigate = useCallback((next: View, folder = "") => {
    setView(next);
    setActiveFolder(folder);
    setJobId("");
    setQuery("");
    setKind("");
    setTag("");
    setSelected([]);
    setSelecting(false);
    setPage(1);
    setSidebarOpen(false);
  }, []);
  const handleXhsConnected = useCallback(() => {
    setQROpen(false);
    setDetail(null);
    navigate("library");
    refresh();
  }, [navigate, refresh]);
  function openJob(id: string) {
    setView("capture");
    setJobId(id);
    setActiveFolder("");
    setSelected([]);
    setQuery("");
    setTag("");
    setKind("");
  }
  function editFolder(folder: Folder | "new") {
    setFolderEditor(folder);
    setFolderName(folder === "new" ? "" : folder.name);
    setFolderParent(folder === "new" ? activeFolder : folder.parent_id || "");
  }
  async function organize(action: string, ids: string[], value = "") {
    await api("/organize", { action, note_ids: ids, value });
    refresh();
  }
  function openOrganize(action: string, ids: string[]) {
    setOrganization({ action, ids });
    setOrgValue(
      action.endsWith("folder")
        ? activeFolder || overview.folders[0]?.id || ""
        : "",
    );
  }
  function exportNotes(ids: string[], folder = "") {
    setExportIds(ids);
    setExportFolder(folder);
  }
  async function perform(action: () => Promise<unknown>, text: string) {
    setBusy(true);
    // Clear the old selection before the request, preserving anything selected while it runs.
    setSelected([]);
    try {
      await action();
      notify(text);
      refresh();
    } catch (e) {
      notify((e as Error).message, true);
    } finally {
      setBusy(false);
    }
  }
  async function drop(event: DragEndEvent) {
    setDragLabel("");
    if (!event.over) return;
    const folder = String(event.over.id).replace("drop:", "");
    const data = event.active.data.current;
    if (!data) return;
    if (data.type === "note") {
      if (folder === "root") return;
      await perform(
        () => organize("add_folder", data.ids, folder),
        "已放入文件夹",
      );
    } else {
      const current = overview.folders.find((f) => f.id === data.id);
      if (!current) return;
      await perform(
        () =>
          api(
            `/folders/${data.id}`,
            {
              name: current.name,
              parent_id: folder === "root" ? null : folder,
            },
            "PATCH",
          ),
        "文件夹已移动",
      );
    }
  }
  const activeName = overview.folders.find((f) => f.id === activeFolder)?.name;
  const pageTitles: Record<View, [string, string]> = {
    library: ["总素材库", "把每一次发现，变成自己的积累。"],
    capture: ["采集", "从一个链接开始，收集值得留下的内容。"],
    tasks: ["任务中心", "查看采集与识别进度，让每一步都有迹可循。"],
    trash: ["回收站", "这里的素材可以恢复，清空后将永久删除本地文件。"],
    settings: ["设置", "管理账号连接与识别服务，打造自己的工作台。"],
  };
  const isGrid = view === "library" || view === "trash" || !!jobId;
  const selectedAll =
    notes.length > 0 && notes.every((n) => selected.includes(n.id));
  const filteredJobs = jobs.filter(
    (job) =>
      taskFilter === "all" ||
      (taskFilter === "active"
        ? ["running", "queued", "waiting_login"].includes(job.state)
        : taskFilter === "attention"
          ? ["failed", "paused"].includes(job.state)
          : job.state === "completed"),
  );
  const jobControls = (job: Job) => (
    <div className="job-controls">
      {["queued", "running", "waiting_login"].includes(job.state) && (
        <Button
          size="icon"
          variant="ghost"
          title="暂停任务"
          aria-label="暂停任务"
          onClick={() =>
            perform(() => api(`/jobs/${job.id}/pause`, {}), "任务已暂停")
          }
        >
          <Pause size={16} />
        </Button>
      )}
      {["paused", "waiting_login"].includes(job.state) && (
        <Button
          size="icon"
          variant="ghost"
          aria-label="继续任务"
          title="继续任务"
          onClick={() =>
            job.state === "waiting_login"
              ? setQROpen(true)
              : perform(() => api(`/jobs/${job.id}/resume`, {}), "任务将继续")
          }
        >
          <Play size={16} />
        </Button>
      )}
      {job.state === "failed" && (
        <Button
          size="sm"
          variant="secondary"
          onClick={() =>
            perform(() => api(`/jobs/${job.id}/retry`, {}), "已加入重试队列")
          }
        >
          <RefreshCw size={14} />
          重试
        </Button>
      )}
      {["queued", "running", "waiting_login", "paused"].includes(job.state) && (
        <Button
          size="icon"
          variant="ghost"
          aria-label="取消任务"
          title="取消任务"
          onClick={() =>
            setConfirm({
              title: "取消这个任务？",
              text: "已经完成的笔记会保留，未完成部分停止执行。",
              run: async () => {
                await api(`/jobs/${job.id}/cancel`, {});
                refresh();
              },
            })
          }
        >
          <X size={16} />
        </Button>
      )}
    </div>
  );
  if (!auth)
    return authError ? (
      <Empty title="无法连接本地服务" description={authError}>
        <Button onClick={loadAuth}>重试</Button>
      </Empty>
    ) : (
      <Busy text="正在打开工作台…" />
    );
  if (!auth.authenticated)
    return <Auth initialized={auth.initialized} done={loadAuth} />;
  return (
    <DndContext
      sensors={sensors}
      onDragStart={(e) => setDragLabel(e.active.data.current?.label || "素材")}
      onDragEnd={drop}
      onDragCancel={() => setDragLabel("")}
    >
      <div className="workspace">
        {sidebarOpen && (
          <button
            className="sidebar-scrim"
            aria-label="关闭导航"
            onClick={() => setSidebarOpen(false)}
          />
        )}
        <aside
          ref={sidebarRef}
          className={`sidebar ${sidebarOpen ? "sidebar-open" : ""}`}
        >
          <button
            className="sidebar-close"
            aria-label="关闭侧栏"
            onClick={() => setSidebarOpen(false)}
          >
            <X size={18} />
          </button>
          <Brand />
          <button className="new-capture" onClick={() => navigate("capture")}>
            <Plus size={18} />
            新建采集<span>＋</span>
          </button>
          <span className="nav-eyebrow">WORKSPACE</span>
          <nav className="primary-nav" aria-label="主导航">
            {(["library", "capture", "tasks"] as View[]).map((v) => {
              const Icon = icons[v];
              return (
                <button
                  className={view === v && !activeFolder ? "active" : ""}
                  key={v}
                  onClick={() => navigate(v)}
                >
                  <Icon size={18} />
                  <span>
                    {v === "library"
                      ? "全部素材"
                      : v === "capture"
                        ? "链接采集"
                        : "任务中心"}
                  </span>
                  {v === "library" && <small>{overview.total}</small>}
                  {v === "tasks" && overview.running_jobs > 0 && (
                    <small className="count-accent">
                      {overview.running_jobs}
                    </small>
                  )}
                </button>
              );
            })}
          </nav>
          <div className="sidebar-divider" />
          <div className="folder-section">
            <RootDrop>
              <div className="section-head">
                <span>我的文件夹</span>
                <button
                  aria-label="新建文件夹"
                  title="新建文件夹"
                  onClick={() => editFolder("new")}
                >
                  <Plus size={16} />
                </button>
              </div>
            </RootDrop>
            <div className="folder-tree">
              {overview.folders
                .filter((f) => !f.parent_id)
                .map((f) => (
                  <FolderRow
                    key={f.id}
                    folder={f}
                    folders={overview.folders}
                    active={activeFolder}
                    select={(id) => navigate("library", id)}
                    edit={editFolder}
                  />
                ))}
              {!overview.folders.length && (
                <button
                  className="folder-empty"
                  onClick={() => editFolder("new")}
                >
                  <FolderPlus size={17} />
                  创建你的第一个文件夹
                </button>
              )}
            </div>
          </div>
          <div className="sidebar-bottom">
            <nav className="primary-nav">
              {(["trash", "settings"] as View[]).map((v) => {
                const Icon = icons[v];
                return (
                  <button
                    key={v}
                    className={view === v ? "active" : ""}
                    onClick={() => navigate(v)}
                  >
                    <Icon size={17} />
                    <span>{v === "trash" ? "回收站" : "设置"}</span>
                    {v === "trash" && overview.trash > 0 && (
                      <small>{overview.trash}</small>
                    )}
                  </button>
                );
              })}
            </nav>
            <div className="local-card">
              <span className="status-dot" />
              <div>
                <strong>本地工作台</strong>
                <small>素材安全保存在这台电脑</small>
              </div>
              <ShieldCheck size={17} />
            </div>
            <div className="profile">
              <span className="profile-avatar">
                {auth.username.slice(0, 1)}
              </span>
              <div>
                <strong>{auth.username}</strong>
                <small>个人空间</small>
              </div>
              <button
                aria-label="退出登录"
                title="退出登录"
                onClick={() =>
                  perform(async () => {
                    await api("/auth/logout", {});
                    loadAuth();
                  }, "已退出登录")
                }
              >
                <LogOut size={16} />
              </button>
            </div>
          </div>
        </aside>
        <div className="main-shell" inert={sidebarOpen || undefined}>
          <header className="topbar">
            <button
              className="mobile-menu"
              aria-label="打开导航"
              onClick={() => setSidebarOpen(!sidebarOpen)}
            >
              <Layers3 size={20} />
            </button>
            <div className="breadcrumb">
              <BookOpen size={15} />
              <span>个人工作台</span>
              <ChevronRight size={13} />
              <strong>{activeName || pageTitles[view][0]}</strong>
            </div>
            <div className="topbar-right">
              <button
                className="command-search"
                onClick={() => {
                  navigate("library");
                  setFocusSearch(true);
                }}
                aria-label="快速查找素材"
              >
                <Search size={16} />
                <span>快速查找</span>
                <kbd>⌘ K</kbd>
              </button>
              <span className="local-badge">
                <span className="status-dot" />
                仅本机访问
              </span>
              <button
                className={`connection ${overview.xhs.state === "valid" ? "connected" : ""}`}
                onClick={() => setQROpen(true)}
              >
                <span className="connection-dot" />
                {overview.xhs.state === "valid"
                  ? overview.xhs.nickname || "小红书已连接"
                  : overview.xhs.state === "unverified"
                    ? "验证小红书连接"
                    : "连接小红书"}
                <ChevronDown size={13} />
              </button>
            </div>
          </header>
          <main className="page-main">
            <section className="page-heading">
              <div>
                <span className="eyebrow">
                  {jobId
                    ? "COLLECTION RESULTS"
                    : activeFolder
                      ? "YOUR COLLECTION"
                      : {
                          library: "THE COLLECTION",
                          capture: "COLLECT & CURATE",
                          tasks: "IN PROGRESS",
                          trash: "RECENTLY REMOVED",
                          settings: "YOUR WORKSPACE",
                        }[view]}
                </span>
                <h1>
                  {jobId ? "采集结果" : activeName || pageTitles[view][0]}
                  {isGrid && <span className="heading-count">{total}</span>}
                </h1>
                <p>
                  {jobId
                    ? "已入库的笔记可以直接打开查看，任务进度会自动更新。"
                    : activeName
                      ? "把相关的素材放在一起，让思路慢慢成形。"
                      : pageTitles[view][1]}
                </p>
              </div>
              <div className="heading-actions">
                {jobId ? (
                  <Button
                    variant="secondary"
                    onClick={() => {
                      setJobId("");
                      navigate("tasks");
                    }}
                  >
                    <ArrowLeft size={16} />
                    返回任务
                  </Button>
                ) : view === "library" ? (
                  <>
                    <Button
                      variant="secondary"
                      onClick={() =>
                        activeFolder
                          ? exportNotes([], activeFolder)
                          : selected.length
                            ? exportNotes(selected)
                            : notify("先选择需要导出的笔记")
                      }
                    >
                      <Download size={16} />
                      导出{selected.length ? ` ${selected.length} 条` : ""}
                    </Button>
                    <Button onClick={() => navigate("capture")}>
                      <Plus size={17} />
                      添加素材
                    </Button>
                  </>
                ) : view === "trash" && overview.trash > 0 ? (
                  <Button
                    variant="destructive"
                    onClick={() =>
                      setConfirm({
                        title: "永久清空回收站？",
                        text: `将删除回收站中的 ${overview.trash} 条笔记及对应本地文件。此操作无法恢复。`,
                        run: async () => {
                          await api("/trash/purge", { note_ids: [] });
                          refresh();
                        },
                      })
                    }
                  >
                    <Trash2 size={16} />
                    清空回收站
                  </Button>
                ) : view === "tasks" ? (
                  <Button onClick={() => navigate("capture")}>
                    <Plus size={16} />
                    新建采集
                  </Button>
                ) : null}
              </div>
            </section>
            {overview.xhs.state === "expired" && (
              <div className="login-banner">
                <QrCode size={20} />
                <div>
                  <strong>小红书需要重新登录</strong>
                  <span>采集进度已保存，扫码后将自动继续。</span>
                </div>
                <Button size="sm" onClick={() => setQROpen(true)}>
                  扫码恢复
                </Button>
              </div>
            )}
            {view === "capture" && !jobId && (
              <Capture notify={notify} refresh={refresh} openJob={openJob} />
            )}
            {view === "settings" && (
              <Settings
                overview={overview}
                notify={notify}
                connect={() => setQROpen(true)}
                refresh={refresh}
              />
            )}
            {view === "library" && !activeFolder && !jobId && (
              <div className="library-summary">
                <button
                  className={!kind ? "active" : ""}
                  onClick={() => setKind("")}
                >
                  <Layers3 size={17} />
                  全部素材<b>{overview.total}</b>
                </button>
                <button
                  className={kind === "图集" ? "active" : ""}
                  onClick={() => setKind("图集")}
                >
                  <ImageIcon size={17} />
                  图文<b>{overview.images}</b>
                </button>
                <button
                  className={kind === "视频" ? "active" : ""}
                  onClick={() => setKind("视频")}
                >
                  <Film size={17} />
                  视频<b>{overview.videos}</b>
                </button>
                <span className="summary-meta">
                  <ScanText size={15} />
                  {overview.ocr} 条已识别文字
                </span>
              </div>
            )}
            {jobId && jobDetail && (
              <div className="job-result-summary">
                <span className={`job-state ${jobDetail.state}`}>
                  {states[jobDetail.state]}
                </span>
                <div>
                  <strong>{jobDetail.title}</strong>
                  <p>{jobDetail.message}</p>
                </div>
                <span className="job-fraction">
                  {jobDetail.done} / {jobDetail.total}
                </span>
                {jobControls(jobDetail)}
              </div>
            )}
            {isGrid && (
              <>
                <div className="library-toolbar">
                  <label className="search-field">
                    <Search size={17} />
                    <input
                      id="library-search"
                      ref={searchRef}
                      aria-label="搜索素材"
                      placeholder="寻找一份灵感：标题、正文、标签…"
                      value={query}
                      onChange={(e) => setQuery(e.target.value)}
                    />
                    {loading && query && (
                      <LoaderCircle
                        size={15}
                        className="spin"
                        aria-label="正在搜索"
                      />
                    )}
                    {query && (
                      <button
                        aria-label="清空搜索"
                        onClick={() => setQuery("")}
                      >
                        <X size={15} />
                      </button>
                    )}
                  </label>
                  <div className="filters">
                    {(view !== "library" || activeFolder) && (
                      <label>
                        <ListFilter size={15} />
                        <select
                          aria-label="内容类型"
                          value={kind}
                          onChange={(e) => setKind(e.target.value)}
                        >
                          <option value="">全部类型</option>
                          <option value="图集">图文</option>
                          <option value="视频">视频</option>
                        </select>
                      </label>
                    )}
                    <TagFilter
                      value={tag}
                      onChange={setTag}
                      originals={overview.original_tags}
                      personal={overview.tags}
                    />
                    <select
                      aria-label="排序方式"
                      value={sort}
                      onChange={(e) => setSort(e.target.value)}
                    >
                      <option value="newest">最近收录</option>
                      <option value="oldest">最早收录</option>
                      <option value="updated">最近更新</option>
                    </select>
                    <div className="view-switch" aria-label="素材展示方式">
                      <button
                        aria-label="卡片视图"
                        aria-pressed={layout === "gallery"}
                        className={layout === "gallery" ? "active" : ""}
                        onClick={() => setLayout("gallery")}
                      >
                        <LayoutGrid size={17} />
                      </button>
                      <button
                        aria-label="列表视图"
                        aria-pressed={layout === "list"}
                        className={layout === "list" ? "active" : ""}
                        onClick={() => setLayout("list")}
                      >
                        <List size={18} />
                      </button>
                    </div>
                    <button
                      className={`batch-mode ${selecting || selected.length ? "active" : ""}`}
                      aria-label={selecting ? "完成多选" : "批量整理"}
                      title="批量选择并整理素材"
                      onClick={() => {
                        setSelecting((v) => !v);
                        if (selecting) setSelected([]);
                      }}
                    >
                      <CheckSquare size={16} />
                      <span>{selecting ? "完成" : "多选"}</span>
                    </button>
                  </div>
                </div>
                {(selecting || selected.length > 0 || query || tag) && (
                  <div className="list-meta">
                    {(query || tag) && (
                      <div className="active-filters">
                        <span>正在筛选</span>
                        {query && (
                          <button onClick={() => setQuery("")}>
                            “{query}” <X size={13} />
                          </button>
                        )}
                        {tag && (
                          <button onClick={() => setTag("")}>
                            #{tag.slice(tag.indexOf(":") + 1)} <X size={13} />
                          </button>
                        )}
                        <button
                          className="reset-filters"
                          onClick={() => {
                            setQuery("");
                            setTag("");
                            setKind("");
                          }}
                        >
                          清除筛选
                        </button>
                      </div>
                    )}
                    <label className="checkbox-label">
                      <input
                        type="checkbox"
                        aria-label="选择当前页全部笔记"
                        checked={selectedAll}
                        onChange={() =>
                          setSelected(selectedAll ? [] : notes.map((n) => n.id))
                        }
                      />
                      {selected.length
                        ? `已选择 ${selected.length} 条`
                        : `共 ${total} 条素材`}
                    </label>
                    <div className="list-meta-actions">
                      <span>选择后可归入文件夹、识别文字或导出</span>
                    </div>
                  </div>
                )}
                {loadError ? (
                  <Empty title="素材加载失败" description={loadError}>
                    <Button onClick={refresh}>重新加载</Button>
                  </Empty>
                ) : loading && !notes.length ? (
                  <div
                    className="skeleton-grid"
                    aria-label="正在加载素材"
                    role="status"
                  >
                    {Array.from({ length: 8 }, (_, i) => (
                      <div className="skeleton-card" key={i}>
                        <div />
                        <span />
                        <span />
                      </div>
                    ))}
                  </div>
                ) : notes.length ? (
                  <div
                    className={`note-grid ${layout === "list" ? "list-view" : ""}`}
                    data-selecting={selecting || selected.length > 0}
                  >
                    {notes.map((note, index) => (
                      <NoteCard
                        key={note.id}
                        note={note}
                        index={(page - 1) * 40 + index}
                        selected={selected.includes(note.id)}
                        selection={selected}
                        toggle={() =>
                          setSelected((ids) =>
                            ids.includes(note.id)
                              ? ids.filter((id) => id !== note.id)
                              : [...ids, note.id],
                          )
                        }
                        open={() => setDetail(note.id)}
                      />
                    ))}
                  </div>
                ) : (
                  <Empty
                    title={
                      view === "trash"
                        ? "回收站是空的"
                        : query || tag || kind
                          ? "没有找到匹配的素材"
                          : jobId
                            ? "等待第一条素材入库"
                            : activeFolder
                              ? "给这个文件夹添点灵感"
                              : "开始收集你的第一份灵感"
                    }
                    description={
                      jobId
                        ? "采集完成的笔记会逐条出现在这里。可在上方查看任务状态。"
                        : activeFolder
                          ? "从总素材库选择笔记，或拖动卡片放进这个文件夹。"
                          : query || tag || kind
                            ? "试试调整关键词或筛选条件。"
                            : view === "trash"
                              ? "删除的素材会先来到这里，清空前都可以恢复。"
                              : "粘贴一个小红书链接，图片、视频和正文都会收纳在这里。"
                    }
                  >
                    {!query && !tag && !kind && !jobId && view !== "trash" && (
                      <Button
                        variant="secondary"
                        onClick={() =>
                          navigate(activeFolder ? "library" : "capture")
                        }
                      >
                        {activeFolder ? "前往总素材库" : "添加素材"}
                        <ArrowUpRight size={16} />
                      </Button>
                    )}
                  </Empty>
                )}
                {total > 40 && (
                  <div className="pagination">
                    <Button
                      variant="secondary"
                      size="sm"
                      disabled={page === 1}
                      onClick={() => setPage((p) => p - 1)}
                    >
                      <ChevronLeft size={16} />
                      上一页
                    </Button>
                    <span>
                      {page} / {Math.ceil(total / 40)}
                    </span>
                    <Button
                      variant="secondary"
                      size="sm"
                      disabled={page * 40 >= total}
                      onClick={() => setPage((p) => p + 1)}
                    >
                      下一页
                      <ChevronRight size={16} />
                    </Button>
                  </div>
                )}
                {jobDetail?.items?.some((i) => i.state === "failed") && (
                  <details className="failed-items">
                    <summary>查看失败项目</summary>
                    {jobDetail.items
                      .filter((i) => i.state === "failed")
                      .map((i) => (
                        <p key={i.id}>
                          <strong>{i.note_id}</strong> {i.message}
                        </p>
                      ))}
                  </details>
                )}
              </>
            )}
            {(view === "tasks" || (view === "capture" && !jobId)) && (
              <section className="jobs-section">
                {view === "tasks" && (
                  <div className="task-filter-tabs segmented">
                    {[
                      ["all", "全部任务"],
                      ["active", "进行中"],
                      ["attention", "待处理"],
                      ["completed", "已完成"],
                    ].map(([value, label]) => (
                      <button
                        key={value}
                        className={taskFilter === value ? "active" : ""}
                        onClick={() => setTaskFilter(value)}
                      >
                        {label}
                      </button>
                    ))}
                  </div>
                )}
                <div className="section-heading">
                  <h2>
                    {view === "tasks"
                      ? {
                          all: "全部任务",
                          active: "进行中的任务",
                          attention: "待处理任务",
                          completed: "已完成任务",
                        }[taskFilter]
                      : "最近任务"}
                    <small>
                      {view === "tasks" ? filteredJobs.length : jobs.length}
                    </small>
                  </h2>
                  <span>关闭页面后，后台任务仍会继续</span>
                </div>
                {!(view === "capture" ? jobs : filteredJobs).length ? (
                  <Empty
                    icon={Clock3}
                    title={jobs.length ? "这个分类下还没有任务" : "还没有任务"}
                    description={
                      jobs.length
                        ? "切换上方分类，查看其他任务的进度与结果。"
                        : "创建采集或 OCR 任务后，可以在这里查看进度和结果。"
                    }
                  />
                ) : (
                  <div className="jobs-list">
                    {(view === "capture" ? jobs.slice(0, 6) : filteredJobs).map(
                      (job) => (
                        <div className="job-row" key={job.id}>
                          <span className={`job-icon ${job.state}`}>
                            {job.state === "running" ? (
                              <LoaderCircle className="spin" size={20} />
                            ) : job.kind === "ocr" ? (
                              <ScanText size={20} />
                            ) : (
                              <Link2 size={20} />
                            )}
                          </span>
                          <button
                            className="job-info"
                            onClick={() => openJob(job.id)}
                          >
                            <strong>{job.title}</strong>
                            <small>{job.message}</small>
                            <div className="progress-track">
                              <i
                                style={{
                                  width: `${job.total ? (job.done / job.total) * 100 : 0}%`,
                                }}
                              />
                            </div>
                          </button>
                          <div className="job-numbers">
                            <span>
                              {job.done}
                              <small> / {job.total}</small>
                            </span>
                            <small>{date(job.created_at)}</small>
                          </div>
                          <span className={`job-state ${job.state}`}>
                            {states[job.state]}
                          </span>
                          {jobControls(job)}
                          <Button
                            size="icon"
                            variant="ghost"
                            aria-label={`查看任务 ${job.title}`}
                            onClick={() => openJob(job.id)}
                          >
                            <ArrowUpRight size={18} />
                          </Button>
                        </div>
                      ),
                    )}
                  </div>
                )}
              </section>
            )}
            <footer className="page-footer">
              <span>拾页 · 每一份灵感，都有归处</span>
              <span>LOCAL FIRST. ALWAYS YOURS.</span>
            </footer>
          </main>
        </div>
      </div>
      {selected.length > 0 && isGrid && (
        <div className="selection-bar">
          <span>
            <CheckCheck size={18} />
            {selected.length} 条已选
          </span>
          <i />
          {view === "trash" ? (
            <>
              <Button
                variant="ghost"
                onClick={() =>
                  perform(() => organize("restore", selected), "笔记已恢复")
                }
              >
                <RefreshCw size={16} />
                恢复
              </Button>
              <Button
                variant="ghost"
                onClick={() =>
                  setConfirm({
                    title: "永久删除所选素材？",
                    text: "对应的本地文件也将被永久删除，无法恢复。",
                    run: async () => {
                      await api("/trash/purge", { note_ids: selected });
                      setSelected([]);
                      refresh();
                    },
                  })
                }
              >
                <Trash2 size={16} />
                永久删除
              </Button>
            </>
          ) : (
            <>
              <Button
                variant="ghost"
                onClick={() => openOrganize("add_folder", selected)}
              >
                <FolderPlus size={16} />
                放入文件夹
              </Button>
              {activeFolder && (
                <Button
                  variant="ghost"
                  onClick={() =>
                    perform(
                      () => organize("remove_folder", selected, activeFolder),
                      "已移出文件夹",
                    )
                  }
                >
                  <FolderIcon size={16} />
                  移出
                </Button>
              )}
              <Button
                variant="ghost"
                onClick={() => openOrganize("add_tag", selected)}
              >
                <Tags size={16} />
                标签
              </Button>
              <Button
                variant="ghost"
                onClick={() =>
                  perform(
                    () => api("/jobs", { kind: "ocr", note_ids: selected }),
                    "已创建 OCR 任务",
                  )
                }
              >
                <ScanText size={16} />
                OCR
              </Button>
              <Button
                variant="ghost"
                onClick={() =>
                  perform(
                    () => api("/jobs", { kind: "refresh", note_ids: selected }),
                    "已创建刷新任务",
                  )
                }
              >
                <RefreshCw size={16} />
                刷新
              </Button>
              <Button variant="ghost" onClick={() => exportNotes(selected)}>
                <Download size={16} />
                导出
              </Button>
              <Button
                variant="ghost"
                onClick={() =>
                  perform(() => organize("trash", selected), "已移入回收站")
                }
              >
                <Trash2 size={16} />
                <span className="sr-only">移入回收站</span>
              </Button>
            </>
          )}
          <button
            className="selection-close"
            aria-label="取消选择"
            onClick={() => setSelected([])}
          >
            <X size={17} />
          </button>
        </div>
      )}
      {toast && (
        <div
          className={`toast ${toast.error ? "error" : ""}`}
          role={toast.error ? "alert" : "status"}
        >
          {toast.error ? <XCircle size={18} /> : <CheckCircle2 size={18} />}
          <span>{toast.text}</span>
          <button aria-label="关闭通知" onClick={() => setToast(null)}>
            <X size={14} />
          </button>
        </div>
      )}
      <NoteModal
        id={detail}
        close={() => setDetail(null)}
        overview={overview}
        refresh={revision}
        notify={notify}
        exportNotes={exportNotes}
        organize={openOrganize}
      />
      <QRDialog
        open={qrOpen}
        close={() => setQROpen(false)}
        connected={handleXhsConnected}
        notify={notify}
      />
      <ExportDialog
        ids={exportIds}
        folder={exportFolder}
        close={() => setExportIds(null)}
        notify={notify}
      />
      <Dialog
        open={!!folderEditor}
        onOpenChange={(v) => !v && setFolderEditor(null)}
        title={folderEditor === "new" ? "新建文件夹" : "管理文件夹"}
        description="文件夹用来归类素材，同一条笔记可以属于多个文件夹。"
      >
        <form
          onSubmit={async (e) => {
            e.preventDefault();
            setBusy(true);
            try {
              await api(
                folderEditor === "new"
                  ? "/folders"
                  : `/folders/${(folderEditor as Folder).id}`,
                { name: folderName, parent_id: folderParent || null },
                folderEditor === "new" ? "POST" : "PATCH",
              );
              setFolderEditor(null);
              refresh();
              notify("文件夹已保存");
            } catch (e) {
              notify((e as Error).message, true);
            } finally {
              setBusy(false);
            }
          }}
        >
          <label>
            文件夹名称
            <input
              autoFocus
              required
              maxLength={100}
              placeholder="例如：选题参考"
              value={folderName}
              onChange={(e) => setFolderName(e.target.value)}
            />
          </label>
          <label>
            所在位置
            <select
              value={folderParent}
              onChange={(e) => setFolderParent(e.target.value)}
            >
              <option value="">我的文件夹（顶层）</option>
              {overview.folders
                .filter(
                  (f) => folderEditor === "new" || f.id !== folderEditor?.id,
                )
                .map((f) => (
                  <option value={f.id} key={f.id}>
                    {f.name}
                  </option>
                ))}
            </select>
          </label>
          <div className="dialog-actions">
            {folderEditor && folderEditor !== "new" && (
              <Button
                variant="ghost"
                type="button"
                className="danger-text mr-auto"
                onClick={() => {
                  const id = folderEditor.id;
                  setFolderEditor(null);
                  setConfirm({
                    title: "删除这个文件夹？",
                    text: "子文件夹也将删除，其中的笔记仍保留在总素材库。",
                    run: async () => {
                      await api(`/folders/${id}`, undefined, "DELETE");
                      navigate("library");
                      refresh();
                    },
                  });
                }}
              >
                <Trash2 size={16} />
                删除文件夹
              </Button>
            )}
            <Button
              variant="secondary"
              type="button"
              onClick={() => setFolderEditor(null)}
            >
              取消
            </Button>
            <Button type="submit" disabled={busy}>
              保存
            </Button>
          </div>
        </form>
      </Dialog>
      <Dialog
        open={!!organization}
        onOpenChange={(v) => !v && setOrganization(null)}
        title={
          organization?.action.endsWith("folder")
            ? "放入文件夹"
            : "管理个人标签"
        }
        description={`为 ${organization?.ids.length || 0} 条笔记整理归类。`}
      >
        <form
          onSubmit={async (e) => {
            e.preventDefault();
            if (!organization) return;
            setBusy(true);
            try {
              await organize(organization.action, organization.ids, orgValue);
              setOrganization(null);
              notify("整理已保存");
            } catch (e) {
              notify((e as Error).message, true);
            } finally {
              setBusy(false);
            }
          }}
        >
          {organization?.action.endsWith("folder") ? (
            <label>
              目标文件夹
              <select
                required
                value={orgValue}
                onChange={(e) => setOrgValue(e.target.value)}
              >
                <option value="">请选择文件夹</option>
                {overview.folders.map((f) => (
                  <option key={f.id} value={f.id}>
                    {f.name}
                  </option>
                ))}
              </select>
              {!overview.folders.length && (
                <small>请先在左侧创建一个文件夹。</small>
              )}
            </label>
          ) : (
            <>
              <label>
                标签
                <input
                  required
                  maxLength={80}
                  list="personal-tags"
                  value={orgValue}
                  onChange={(e) => setOrgValue(e.target.value)}
                  placeholder="例如：下次拍摄参考"
                />
                <datalist id="personal-tags">
                  {overview.tags.map((t) => (
                    <option key={t} value={t} />
                  ))}
                </datalist>
              </label>
              <label>
                操作
                <select
                  value={organization?.action || "add_tag"}
                  onChange={(e) =>
                    setOrganization(
                      (o) => o && { ...o, action: e.target.value },
                    )
                  }
                >
                  <option value="add_tag">添加标签</option>
                  <option value="remove_tag">移除标签</option>
                </select>
              </label>
            </>
          )}
          <div className="dialog-actions">
            <Button
              variant="secondary"
              type="button"
              onClick={() => setOrganization(null)}
            >
              取消
            </Button>
            <Button disabled={busy || !orgValue} type="submit">
              确定
            </Button>
          </div>
        </form>
      </Dialog>
      <Dialog
        open={!!confirm}
        onOpenChange={(v) => !v && !busy && setConfirm(null)}
        title={confirm?.title || "确认操作"}
        description={confirm?.text}
      >
        <div className="dialog-actions">
          <Button
            variant="secondary"
            disabled={busy}
            onClick={() => setConfirm(null)}
          >
            取消
          </Button>
          <Button
            variant="destructive"
            disabled={busy}
            onClick={async () => {
              if (!confirm) return;
              setBusy(true);
              try {
                await confirm.run();
                setConfirm(null);
                notify("操作完成");
              } catch (e) {
                notify((e as Error).message, true);
              } finally {
                setBusy(false);
              }
            }}
          >
            确认
          </Button>
        </div>
      </Dialog>
      <DragOverlay>
        {dragLabel && (
          <div className="drag-preview">
            <FolderPlus size={17} />
            <span>{dragLabel}</span>
          </div>
        )}
      </DragOverlay>
    </DndContext>
  );
}

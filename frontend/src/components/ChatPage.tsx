import {
  useCallback,
  useEffect,
  useRef,
  useState,
  type KeyboardEvent,
} from "react";
import Markdown from "react-markdown";
import remarkGfm from "remark-gfm";
import {
  ArrowDown,
  ArrowUp,
  ArrowUpRight,
  AtSign,
  Check,
  ChevronDown,
  Copy,
  FileText,
  Film,
  History,
  LoaderCircle,
  MessageSquare,
  Pencil,
  Plus,
  Search,
  Settings2,
  Sparkles,
  Square,
  Trash2,
  X,
} from "lucide-react";
import { api, date, safeLink, type Folder, type Note } from "../api";
import {
  isGenerating,
  type AIModel,
  type ChatDetail,
  type ChatMessage,
  type ChatSource,
  type ChatThread,
} from "../chat";
import { Button } from "./ui/button";
import { Dialog } from "./ui/dialog";

type Notice = (text: string, error?: boolean) => void;
type Launch = { nonce: number; ids: string[] } | null;
const suggestions = [
  [
    "交叉对比",
    "比较观点，找到交集与分歧",
    "请对比这些素材的核心观点，整理共同点、分歧和各自的依据。",
  ],
  [
    "提炼要点",
    "从收藏中梳理一份行动清单",
    "请提炼这些素材最值得保留的要点，并给我一份可执行的行动清单。",
  ],
  [
    "转成创作",
    "把零散灵感，串成一份提纲",
    "请基于这些素材，给我一份原创内容提纲，并标注参考了哪些素材。",
  ],
];

function SourceIcon({ source }: { source: ChatSource }) {
  return source.cover ? (
    <img src={source.cover} alt="" />
  ) : source.kind === "视频" ? (
    <Film size={16} />
  ) : (
    <FileText size={16} />
  );
}

function MaterialPicker({
  open,
  close,
  selected,
  setSelected,
  folders,
  notify,
}: {
  open: boolean;
  close: () => void;
  selected: ChatSource[];
  setSelected: (items: ChatSource[]) => void;
  folders: Folder[];
  notify: Notice;
}) {
  const [query, setQuery] = useState(""),
    [kind, setKind] = useState(""),
    [folder, setFolder] = useState("");
  const [items, setItems] = useState<Note[]>([]),
    [total, setTotal] = useState(0),
    [page, setPage] = useState(1),
    [loading, setLoading] = useState(false),
    [error, setError] = useState("");
  useEffect(() => {
    setPage(1);
  }, [query, kind, folder]);
  useEffect(() => {
    if (!open) return;
    let active = true;
    setLoading(true);
    setError("");
    const timer = setTimeout(() => {
      api<{ items: Note[]; total: number }>(
        `/notes?${new URLSearchParams({ q: query, kind, folder, page: String(page), page_size: "30" })}`,
      )
        .then((data) => {
          if (active) {
            setItems(data.items);
            setTotal(data.total);
          }
        })
        .catch((e) => active && setError(e.message))
        .finally(() => active && setLoading(false));
    }, 180);
    return () => {
      active = false;
      clearTimeout(timer);
    };
  }, [open, query, kind, folder, page]);
  function toggle(note: ChatSource) {
    if (selected.some((s) => s.id === note.id))
      setSelected(selected.filter((s) => s.id !== note.id));
    else if (selected.length >= 8) notify("每次最多引用 8 份素材", true);
    else setSelected([...selected, note]);
  }
  return (
    <Dialog
      open={open}
      onOpenChange={(v) => !v && close()}
      title="引用素材"
      description="选择图文或视频，带进这次对话。每轮最多 8 份。"
      className="material-picker"
    >
      <div className="material-search">
        <Search size={17} />
        <input
          aria-label="搜索要引用的素材"
          placeholder="搜索标题、正文、作者或标签"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
        />
      </div>
      <div className="material-filters">
        <div>
          {[
            ["", "全部"],
            ["图集", "图文"],
            ["视频", "视频"],
          ].map(([value, label]) => (
            <button
              key={value}
              className={kind === value ? "active" : ""}
              onClick={() => setKind(value)}
            >
              {label}
            </button>
          ))}
        </div>
        <select
          aria-label="按文件夹筛选素材"
          value={folder}
          onChange={(e) => setFolder(e.target.value)}
        >
          <option value="">所有文件夹</option>
          {folders.map((f) => (
            <option key={f.id} value={f.id}>
              {f.name}
            </option>
          ))}
        </select>
      </div>
      <div className="material-results" aria-busy={loading}>
        {loading ? (
          <div className="chat-loading">
            <LoaderCircle className="spin" size={20} />
            正在查找素材
          </div>
        ) : error ? (
          <p role="alert" className="chat-empty-small">
            {error}
          </p>
        ) : !items.length ? (
          <p className="chat-empty-small">没有找到素材，试试其他关键词。</p>
        ) : (
          items.map((note) => {
            const checked = selected.some((s) => s.id === note.id);
            return (
              <button
                className={`material-result ${checked ? "selected" : ""}`}
                key={note.id}
                aria-pressed={checked}
                onClick={() => toggle(note)}
              >
                <span className="source-thumb">
                  <SourceIcon source={note} />
                </span>
                <span>
                  <strong>{note.title}</strong>
                  <small>
                    {note.author} ·{" "}
                    {note.kind === "视频"
                      ? "视频"
                      : `${note.image_count} 张图片`}
                    {note.has_ocr ? " · 已有 OCR" : ""}
                  </small>
                </span>
                <span className="material-check">
                  {checked && <Check size={14} />}
                </span>
              </button>
            );
          })
        )}
      </div>
      <div className="material-picker-footer">
        <span>已选 {selected.length} / 8</span>
        {total > 30 && (
          <div className="material-pages">
            <button disabled={page === 1} onClick={() => setPage((p) => p - 1)}>
              上一页
            </button>
            <span>
              {page} / {Math.ceil(total / 30)}
            </span>
            <button
              disabled={page * 30 >= total}
              onClick={() => setPage((p) => p + 1)}
            >
              下一页
            </button>
          </div>
        )}
        <Button onClick={close}>完成选择</Button>
      </div>
    </Dialog>
  );
}

export function ChatPage({
  active,
  launch,
  folders,
  openNote,
  openSettings,
  notify,
}: {
  active: boolean;
  launch: Launch;
  folders: Folder[];
  openNote: (id: string) => void;
  openSettings: () => void;
  notify: Notice;
}) {
  const [threads, setThreads] = useState<ChatThread[]>([]),
    [models, setModels] = useState<AIModel[]>([]);
  const [current, setCurrent] = useState<string | null>(() =>
    launch ? null : localStorage.getItem("shiyi-chat-thread"),
  );
  const [detail, setDetail] = useState<ChatDetail | null>(null),
    [modelId, setModelId] = useState(
      localStorage.getItem("shiyi-chat-model") || "",
    );
  const [sources, setSources] = useState<ChatSource[]>([]),
    [draft, setDraft] = useState(""),
    [picker, setPicker] = useState(false);
  const [sending, setSending] = useState(false),
    [loading, setLoading] = useState(false),
    [loadError, setLoadError] = useState("");
  const [search, setSearch] = useState(""),
    [historyOpen, setHistoryOpen] = useState(false);
  const [mention, setMention] = useState<{
      start: number;
      end: number;
      query: string;
    } | null>(null),
    [matches, setMatches] = useState<Note[]>([]),
    [matchIndex, setMatchIndex] = useState(0);
  const [rename, setRename] = useState<ChatThread | null>(null),
    [title, setTitle] = useState(""),
    [remove, setRemove] = useState<ChatThread | null>(null);
  const [streamError, setStreamError] = useState(""),
    [showLatest, setShowLatest] = useState(false);
  const input = useRef<HTMLTextAreaElement>(null),
    scroll = useRef<HTMLDivElement>(null),
    follow = useRef(true),
    currentRef = useRef(current);
  const pendingSend = useRef<{
    fingerprint: string;
    requestId: string;
    threadId: string | null;
  } | null>(null);
  currentRef.current = current;
  const model = models.find((m) => m.id === modelId),
    messages = detail?.id === current ? detail.messages : [];
  const generating = messages.find(isGenerating);
  const refreshThreads = useCallback(
    () =>
      api<ChatThread[]>("/chat/threads")
        .then(setThreads)
        .catch((e) => notify(e.message, true)),
    [notify],
  );
  useEffect(() => {
    if (!active) return;
    refreshThreads();
    api<AIModel[]>("/settings/ai/models")
      .then((list) => {
        setModels(list);
        setModelId((id) =>
          list.some((m) => m.id === id) ? id : list[0]?.id || "",
        );
      })
      .catch((e) => notify(e.message, true));
  }, [active, refreshThreads, notify]);
  useEffect(() => {
    if (modelId) localStorage.setItem("shiyi-chat-model", modelId);
  }, [modelId]);
  useEffect(() => {
    if (!current) {
      localStorage.removeItem("shiyi-chat-thread");
      setDetail(null);
      return;
    }
    localStorage.setItem("shiyi-chat-thread", current);
    setLoading(true);
    setLoadError("");
    let active = true;
    api<ChatDetail>(`/chat/threads/${current}`)
      .then(async (data) => {
        if (!active) return;
        setDetail(data);
        const found = new Map<string, ChatSource>();
        data.messages.forEach((m) =>
          m.sources.forEach((s) => found.set(s.id, s)),
        );
        setSources(
          data.source_ids.flatMap((id) =>
            found.has(id) ? [found.get(id)!] : [],
          ),
        );
        if (data.model_id)
          setModelId((id) =>
            models.some((m) => m.id === data.model_id) ? data.model_id : id,
          );
        follow.current = true;
      })
      .catch((e) => active && setLoadError(e.message))
      .finally(() => active && setLoading(false));
    return () => {
      active = false;
    };
  }, [current]);
  useEffect(() => {
    if (!launch) return;
    setCurrent(null);
    setDetail(null);
    setDraft("");
    setSources([]);
    let active = true;
    Promise.all(launch.ids.map((id) => api<Note>(`/notes/${id}`)))
      .then((items) => {
        if (active) setSources(items.filter((n) => !n.trashed_at));
      })
      .catch((e) => active && notify(e.message, true));
    return () => {
      active = false;
    };
  }, [launch, notify]);
  useEffect(() => {
    if (!mention) {
      setMatches([]);
      return;
    }
    let active = true;
    setMatchIndex(0);
    const timer = setTimeout(
      () =>
        api<{ items: Note[] }>(
          `/notes?${new URLSearchParams({ q: mention.query, page_size: "6" })}`,
        )
          .then((data) => active && setMatches(data.items))
          .catch(() => active && setMatches([])),
      140,
    );
    return () => {
      active = false;
      clearTimeout(timer);
    };
  }, [mention?.query]);
  useEffect(() => {
    if (!generating) {
      setStreamError("");
      return;
    }
    const messageId = generating.id,
      threadId = current;
    const events = new EventSource(`/api/chat/messages/${messageId}/events`);
    events.onmessage = (event) => {
      if (currentRef.current !== threadId) return;
      const value = JSON.parse(event.data) as ChatMessage;
      setStreamError("");
      setDetail((previous) =>
        previous?.id === threadId
          ? {
              ...previous,
              messages: previous.messages.map((m) =>
                m.id === value.id ? value : m,
              ),
            }
          : previous,
      );
      if (!isGenerating(value)) {
        events.close();
        refreshThreads();
      }
    };
    events.onerror = () => setStreamError("正在重新连接，已生成的内容会保留…");
    return () => events.close();
  }, [generating?.id, current, refreshThreads]);
  useEffect(() => {
    if (!active || !messages.length || !follow.current || !scroll.current)
      return;
    const frame = requestAnimationFrame(() => {
      if (scroll.current)
        scroll.current.scrollTop = scroll.current.scrollHeight;
    });
    return () => cancelAnimationFrame(frame);
  }, [messages, current, active]);

  function fresh() {
    if (sending) return;
    setCurrent(null);
    setDetail(null);
    setDraft("");
    setSources([]);
    setHistoryOpen(false);
    setLoadError("");
    setMention(null);
    if (scroll.current) scroll.current.scrollTop = 0;
    input.current?.focus();
  }
  function selectThread(thread: ChatThread) {
    if (sending) return;
    setCurrent(thread.id);
    setDraft("");
    setMention(null);
    setHistoryOpen(false);
  }
  function addMention(note: Note) {
    if (!sources.some((s) => s.id === note.id)) {
      if (sources.length >= 8) {
        notify("每次最多引用 8 份素材", true);
        return;
      }
      setSources((items) => [...items, note]);
    }
    if (mention)
      setDraft(
        (text) => text.slice(0, mention.start) + text.slice(mention.end),
      );
    setMention(null);
    input.current?.focus();
  }
  function updateDraft(value: string, caret: number) {
    setDraft(value);
    const match = value.slice(0, caret).match(/(?:^|\s)@([^\n@]*)$/);
    setMention(
      match
        ? { start: caret - match[1].length - 1, end: caret, query: match[1] }
        : null,
    );
  }
  function keyboard(event: KeyboardEvent<HTMLTextAreaElement>) {
    if (event.nativeEvent.isComposing || event.keyCode === 229) return;
    if (mention) {
      if (event.key === "Escape") {
        event.preventDefault();
        setMention(null);
        return;
      }
      if (["ArrowDown", "ArrowUp"].includes(event.key)) {
        event.preventDefault();
        setMatchIndex((i) =>
          Math.max(
            0,
            Math.min(
              matches.length - 1,
              i + (event.key === "ArrowDown" ? 1 : -1),
            ),
          ),
        );
        return;
      }
      if (event.key === "Enter" && matches[matchIndex]) {
        event.preventDefault();
        addMention(matches[matchIndex]);
        return;
      }
    }
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      if (!mention) send();
    }
  }
  async function send() {
    if (!draft.trim() || sending || generating) return;
    if (!model) {
      notify("请先在设置中添加并选择对话模型", true);
      return;
    }
    setSending(true);
    setMention(null);
    follow.current = true;
    try {
      const fingerprint = JSON.stringify([
        current,
        draft.trim(),
        sources.map((s) => s.id),
        model.id,
      ]);
      if (pendingSend.current?.fingerprint !== fingerprint) {
        pendingSend.current = {
          fingerprint,
          requestId: crypto.randomUUID().replaceAll("-", ""),
          threadId: current,
        };
      }
      const pending = pendingSend.current;
      if (!pending.threadId)
        pending.threadId = (await api<ChatThread>("/chat/threads", {})).id;
      const threadId = pending.threadId;
      await api<ChatMessage>(`/chat/threads/${threadId}/messages`, {
        request_id: pending.requestId,
        content: draft.trim(),
        note_ids: sources.map((s) => s.id),
        model_id: model.id,
      });
      setDraft("");
      setCurrent(threadId);
      const updated = await api<ChatDetail>(`/chat/threads/${threadId}`);
      setDetail(updated);
      refreshThreads();
    } catch (e) {
      notify((e as Error).message, true);
    } finally {
      setSending(false);
    }
  }
  function retry(message: ChatMessage) {
    const user = messages.find((m) => m.id === message.reply_to);
    if (user) {
      setDraft(user.content);
      setSources(user.sources);
      input.current?.focus();
    }
  }
  async function copy(text: string) {
    try {
      await navigator.clipboard.writeText(text);
      notify("已复制回答");
    } catch {
      notify("复制失败，请手动选择文字复制", true);
    }
  }
  function exportChat() {
    if (!detail) return;
    const text =
      `# ${detail.title}\n\n` +
      detail.messages
        .map(
          (m) =>
            `## ${m.role === "user" ? "我的问题" : m.model_name || "拾页 AI"}\n\n${m.content}\n\n${m.sources.length ? "引用素材：\n" + m.sources.map((s) => `- ${s.title}（${s.author}）${s.coverage ? `：${s.coverage}` : ""}`).join("\n") : ""}`,
        )
        .join("\n\n---\n\n");
    const url = URL.createObjectURL(
        new Blob([text], { type: "text/markdown;charset=utf-8" }),
      ),
      anchor = document.createElement("a");
    anchor.href = url;
    anchor.download = `${detail.title.replace(/[\\/:*?"<>|]/g, "_")}.md`;
    anchor.click();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
  }
  return (
    <div className="chat-workbench">
      <aside
        className={`chat-history ${historyOpen ? "open" : ""}`}
        aria-label="AI 对话历史"
      >
        <div className="chat-history-heading">
          <span>我的对话</span>
          <button
            className="chat-history-close"
            aria-label="关闭对话历史"
            onClick={() => setHistoryOpen(false)}
          >
            <X size={17} />
          </button>
        </div>
        <Button
          className="chat-new"
          variant="secondary"
          onClick={fresh}
          disabled={sending}
        >
          <Plus size={16} />
          新对话
        </Button>
        <div className="chat-history-search">
          <Search size={14} />
          <input
            aria-label="搜索对话历史"
            placeholder="查找对话"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
          />
        </div>
        <span className="chat-history-eyebrow">RECENT CONVERSATIONS</span>
        <div className="chat-history-list">
          {threads
            .filter((t) => t.title.toLowerCase().includes(search.toLowerCase()))
            .map((thread) => (
              <div
                className={`chat-history-row ${current === thread.id ? "active" : ""}`}
                key={thread.id}
              >
                <button
                  className="chat-history-link"
                  onClick={() => selectThread(thread)}
                >
                  <MessageSquare size={15} />
                  <span>
                    {thread.title}
                    <small>{date(thread.updated_at)}</small>
                  </span>
                </button>
                <button
                  className="chat-history-edit"
                  aria-label={`重命名对话 ${thread.title}`}
                  onClick={() => {
                    setRename(thread);
                    setTitle(thread.title);
                  }}
                >
                  <Pencil size={13} />
                </button>
                <button
                  className="chat-history-delete"
                  aria-label={`删除对话 ${thread.title}`}
                  onClick={() => setRemove(thread)}
                >
                  <Trash2 size={13} />
                </button>
              </div>
            ))}
          {!threads.length && (
            <p className="chat-history-empty">
              一次好问题，
              <br />
              让收藏有了新的用处。
            </p>
          )}
        </div>
        <div className="chat-history-foot">
          <span className="status-dot" />
          <span>对话历史保存在本机</span>
        </div>
      </aside>
      {historyOpen && (
        <button
          className="chat-history-scrim"
          aria-label="收起对话历史"
          onClick={() => setHistoryOpen(false)}
        />
      )}
      <section className="chat-stage">
        <header className="chat-toolbar">
          <div>
            <button
              className="chat-history-toggle"
              aria-label="打开对话历史"
              onClick={() => setHistoryOpen(true)}
            >
              <History size={19} />
            </button>
            <span className="chat-brand">
              <Sparkles size={18} />
              <strong>拾页 AI</strong>
            </span>
            <span className="chat-title">{detail?.title || "与灵感对话"}</span>
          </div>
          <div>
            <button
              className="chat-mobile-new"
              aria-label="新对话"
              onClick={fresh}
            >
              <Plus size={19} />
            </button>
            {!!messages.length && (
              <button
                onClick={exportChat}
                aria-label="导出对话 Markdown"
                title="导出对话"
              >
                <ArrowDown size={18} />
              </button>
            )}
            <button
              onClick={openSettings}
              aria-label="配置 AI 模型"
              title="配置模型"
            >
              <Settings2 size={18} />
            </button>
          </div>
        </header>
        <div
          className="chat-scroll"
          ref={scroll}
          onScroll={(e) => {
            const node = e.currentTarget;
            follow.current =
              node.scrollHeight - node.scrollTop - node.clientHeight < 100;
            setShowLatest(!follow.current);
          }}
        >
          {loading ? (
            <div className="chat-loading">
              <LoaderCircle className="spin" size={20} />
              正在读取对话
            </div>
          ) : loadError ? (
            <div className="chat-empty-small" role="alert">
              {loadError}
              <Button variant="ghost" onClick={fresh}>
                开始新对话
              </Button>
            </div>
          ) : !messages.length ? (
            <div className="chat-welcome">
              <div className="chat-welcome-sign">
                @<span>YOUR IDEAS, CONNECTED.</span>
              </div>
              <h1>
                让收藏，
                <br className="chat-title-break" />
                成为你的答案。
              </h1>
              <p>
                带上几份图文或视频。
                <br />
                一起梳理观点、发现联系，写出新的想法。
              </p>
              <div className="chat-suggestions">
                {suggestions.map(([title, description, prompt], index) => (
                  <button
                    key={title}
                    onClick={() => {
                      setDraft(prompt);
                      if (!sources.length) setPicker(true);
                      else input.current?.focus();
                    }}
                  >
                    <span>
                      0{index + 1}
                      <ArrowUpRight size={17} />
                    </span>
                    <strong>{title}</strong>
                    <small>{description}</small>
                  </button>
                ))}
              </div>
            </div>
          ) : (
            <div className="chat-messages" role="log" aria-label="对话内容">
              {messages.map((message) => (
                <article
                  key={message.id}
                  className={`chat-message ${message.role}`}
                >
                  <div className="chat-message-author">
                    {message.role === "assistant" ? (
                      <span className="chat-assistant-mark">
                        <Sparkles size={16} />
                      </span>
                    ) : (
                      <span className="chat-user-mark">我</span>
                    )}
                    <strong>
                      {message.role === "assistant"
                        ? message.model_name || "拾页 AI"
                        : "我的问题"}
                    </strong>
                    {message.role === "assistant" && isGenerating(message) && (
                      <span className="chat-writing">
                        <i />
                        {message.status === "pending"
                          ? "正在读取素材"
                          : "正在生成"}
                      </span>
                    )}
                  </div>
                  {message.role === "user" && !!message.sources.length && (
                    <div className="chat-message-sources">
                      {message.sources.map((source) => (
                        <button
                          key={source.id}
                          onClick={() => openNote(source.id)}
                        >
                          <span className="source-thumb">
                            <SourceIcon source={source} />
                          </span>
                          <span>{source.title}</span>
                          <ArrowUpRight size={12} />
                        </button>
                      ))}
                    </div>
                  )}
                  <div className="chat-prose">
                    {message.role === "user" ? (
                      <p className="chat-user-text">{message.content}</p>
                    ) : message.content ? (
                      <Markdown
                        remarkPlugins={[remarkGfm]}
                        components={{
                          a: ({ href, children }) => {
                            const source = message.sources.find(
                              (s) => href === `#source-${s.id}`,
                            );
                            pendingSend.current = null;
                            return source ? (
                              <button
                                className="chat-citation"
                                onClick={() => openNote(source.id)}
                                title={`查看 ${source.title}`}
                              >
                                <FileText size={12} />
                                {children}
                              </button>
                            ) : safeLink(href) ? (
                              <a
                                href={safeLink(href)}
                                target="_blank"
                                rel="noreferrer"
                              >
                                {children}
                              </a>
                            ) : (
                              <span>{children}</span>
                            );
                          },
                          img: ({ alt }) => <span>{alt || ""}</span>,
                        }}
                      >
                        {message.content}
                      </Markdown>
                    ) : isGenerating(message) ? (
                      <span className="chat-thinking">
                        <i />
                        <i />
                        <i />
                      </span>
                    ) : null}
                  </div>
                  {message.role === "assistant" && !isGenerating(message) && (
                    <>
                      <div className="chat-answer-actions">
                        {!!message.content && (
                          <button onClick={() => copy(message.content)}>
                            <Copy size={14} />
                            复制
                          </button>
                        )}
                        {["error", "stopped"].includes(message.status) && (
                          <button onClick={() => retry(message)}>
                            重新提问
                          </button>
                        )}
                        {message.status === "stopped" && (
                          <span>已停止生成</span>
                        )}
                      </div>
                      {message.error && (
                        <p className="chat-error" role="alert">
                          {message.error}
                        </p>
                      )}
                      {!!message.sources.length && (
                        <details className="chat-evidence">
                          <summary>
                            本轮上下文中的 {message.sources.length} 份素材
                            <ChevronDown size={13} />
                          </summary>
                          <div>
                            {message.sources.map((source) => (
                              <button
                                key={source.id}
                                onClick={() => openNote(source.id)}
                              >
                                <FileText size={14} />
                                <span>
                                  <strong>{source.title}</strong>
                                  <small>
                                    {source.coverage ||
                                      "来自对话中已引用的素材"}
                                  </small>
                                </span>
                                <ArrowUpRight size={13} />
                              </button>
                            ))}
                          </div>
                        </details>
                      )}
                    </>
                  )}
                </article>
              ))}
            </div>
          )}
        </div>
        <div className="chat-compose-wrap">
          {showLatest && (
            <button
              className="chat-scroll-latest"
              onClick={() => {
                follow.current = true;
                scroll.current?.scrollTo({
                  top: scroll.current.scrollHeight,
                  behavior: "smooth",
                });
              }}
            >
              <ArrowDown size={15} />
              回到最新
            </button>
          )}
          {!models.length && (
            <div className="chat-setup-hint">
              <Sparkles size={16} />
              <span>连接一个对话模型，开始你的第一次提问。</span>
              <button onClick={openSettings}>
                配置模型
                <ArrowUpRight size={14} />
              </button>
            </div>
          )}
          {streamError && (
            <p className="chat-stream-notice" role="status">
              {streamError}
            </p>
          )}
          <div className="chat-composer">
            {!!sources.length && (
              <div className="chat-attachments" aria-label="本轮引用的素材">
                {sources.map((source) => (
                  <div className="chat-attachment" key={source.id}>
                    <button onClick={() => openNote(source.id)}>
                      <span className="source-thumb">
                        <SourceIcon source={source} />
                      </span>
                      <span>
                        <strong>{source.title}</strong>
                        <small>
                          {source.kind === "视频"
                            ? model
                              ? model.vision
                                ? "视频 · 抽样画面"
                                : "视频 · 仅文字"
                              : "视频 · 待选模型"
                            : `图文 · ${source.image_count} 图`}
                          {source.has_ocr ? " · OCR" : ""}
                        </small>
                      </span>
                    </button>
                    <button
                      disabled={!!generating || sending}
                      aria-label={`移除附件 ${source.title}`}
                      onClick={() =>
                        setSources((items) =>
                          items.filter((s) => s.id !== source.id),
                        )
                      }
                    >
                      <X size={14} />
                    </button>
                  </div>
                ))}
                <button
                  className="chat-add-more"
                  disabled={!!generating || sending}
                  onClick={() => setPicker(true)}
                  aria-label="继续添加素材"
                >
                  <Plus size={17} />
                </button>
              </div>
            )}
            {mention && (
              <div
                className="chat-mention-menu"
                id="material-mentions"
                role="listbox"
                aria-label="匹配的素材"
              >
                {matches.length ? (
                  matches.map((note, index) => (
                    <button
                      id={`mention-${index}`}
                      key={note.id}
                      role="option"
                      aria-selected={index === matchIndex}
                      className={index === matchIndex ? "active" : ""}
                      onMouseDown={(e) => e.preventDefault()}
                      onClick={() => addMention(note)}
                    >
                      <span className="source-thumb">
                        <SourceIcon source={note} />
                      </span>
                      <span>
                        <strong>{note.title}</strong>
                        <small>
                          {note.author} · {note.kind}
                        </small>
                      </span>
                      {sources.some((s) => s.id === note.id) && (
                        <Check size={14} />
                      )}
                    </button>
                  ))
                ) : (
                  <p>没有匹配的素材，试试其他关键词</p>
                )}
                <button
                  className="chat-mention-browse"
                  onClick={() => {
                    setMention(null);
                    setPicker(true);
                  }}
                >
                  浏览全部素材
                  <ArrowUpRight size={14} />
                </button>
              </div>
            )}
            <textarea
              ref={input}
              value={draft}
              onChange={(e) =>
                updateDraft(e.target.value, e.target.selectionStart)
              }
              onKeyDown={keyboard}
              aria-label="向 AI 提问"
              aria-controls={mention ? "material-mentions" : undefined}
              aria-activedescendant={
                mention && matches.length ? `mention-${matchIndex}` : undefined
              }
              placeholder={
                sources.length
                  ? "想从这些素材里了解什么？"
                  : "提出问题，输入 @ 引用图文或视频…"
              }
              rows={3}
              maxLength={12000}
              disabled={sending || !!generating}
            />
            <div className="chat-compose-actions">
              <div>
                <button
                  className="chat-attach-button"
                  disabled={sending || !!generating}
                  onClick={() => setPicker(true)}
                >
                  <AtSign size={17} />
                  <span>引用素材</span>
                  {!!sources.length && <small>{sources.length}/8</small>}
                </button>
                <span className="chat-compose-divider" />
                <div className="chat-model-select">
                  <Sparkles size={13} />
                  <select
                    aria-label="选择对话模型"
                    value={modelId}
                    disabled={sending || !!generating}
                    onChange={(e) => setModelId(e.target.value)}
                  >
                    {!models.length && <option value="">尚未配置模型</option>}
                    {models.map((item) => (
                      <option key={item.id} value={item.id}>
                        {item.name}
                      </option>
                    ))}
                  </select>
                </div>
              </div>
              {generating ? (
                <button
                  className="chat-send stop"
                  aria-label="停止生成"
                  title="停止生成"
                  onClick={async () => {
                    try {
                      const value = await api<ChatMessage>(
                        `/chat/messages/${generating.id}/stop`,
                        {},
                      );
                      setDetail((d) =>
                        d
                          ? {
                              ...d,
                              messages: d.messages.map((m) =>
                                m.id === value.id ? value : m,
                              ),
                            }
                          : d,
                      );
                    } catch (e) {
                      notify((e as Error).message, true);
                    }
                  }}
                >
                  <Square size={15} />
                </button>
              ) : (
                <button
                  className="chat-send"
                  aria-label="发送问题"
                  title="发送问题"
                  disabled={!draft.trim() || !model || sending || loading}
                  onClick={send}
                >
                  {sending ? (
                    <LoaderCircle size={19} className="spin" />
                  ) : (
                    <ArrowUp size={20} />
                  )}
                </button>
              )}
            </div>
          </div>
          <div className="chat-compose-note">
            <span>
              {!model ? (
                "配置模型后，发送所选资料与近期对话进行分析。"
              ) : (
                <>
                  {model.vision
                    ? sources.some((s) => s.kind === "视频")
                      ? "视频最多抽取 6 帧 / 条，暂不分析音频。"
                      : "图文每条最多 6 张图片，每轮最多 24 张画面。"
                    : "使用原文与已有 OCR 文字，不发送画面。"}{" "}
                  发送所选资料与近期对话至当前模型。
                </>
              )}
            </span>
            <kbd>↵ 发送 · ⇧↵ 换行</kbd>
          </div>
        </div>
      </section>
      <MaterialPicker
        open={picker}
        close={() => setPicker(false)}
        selected={sources}
        setSelected={setSources}
        folders={folders}
        notify={notify}
      />
      <Dialog
        open={!!rename}
        onOpenChange={(v) => !v && setRename(null)}
        title="重命名对话"
      >
        <form
          onSubmit={async (e) => {
            e.preventDefault();
            if (!rename) return;
            try {
              await api(`/chat/threads/${rename.id}`, { title }, "PATCH");
              setThreads((ts) =>
                ts.map((t) => (t.id === rename.id ? { ...t, title } : t)),
              );
              setDetail((d) => (d?.id === rename.id ? { ...d, title } : d));
              setRename(null);
            } catch (e) {
              notify((e as Error).message, true);
            }
          }}
        >
          <label>
            对话名称
            <input
              value={title}
              maxLength={120}
              required
              onChange={(e) => setTitle(e.target.value)}
            />
          </label>
          <div className="dialog-actions">
            <Button type="submit">保存名称</Button>
          </div>
        </form>
      </Dialog>
      <Dialog
        open={!!remove}
        onOpenChange={(v) => !v && setRemove(null)}
        title="删除这段对话？"
        description="对话记录会从本机删除，引用的素材会保留。"
      >
        <div className="dialog-actions">
          <Button variant="ghost" onClick={() => setRemove(null)}>
            取消
          </Button>
          <Button
            variant="destructive"
            onClick={async () => {
              if (!remove) return;
              try {
                await api(`/chat/threads/${remove.id}`, undefined, "DELETE");
                setThreads((ts) => ts.filter((t) => t.id !== remove.id));
                if (current === remove.id) fresh();
                setRemove(null);
              } catch (e) {
                notify((e as Error).message, true);
              }
            }}
          >
            删除对话
          </Button>
        </div>
      </Dialog>
    </div>
  );
}

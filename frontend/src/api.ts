export async function api<T = Record<string, unknown>>(
  url: string,
  data?: unknown,
  method?: string,
): Promise<T> {
  const response = await fetch(`/api${url}`, {
    method: method || (data === undefined ? "GET" : "POST"),
    credentials: "same-origin",
    headers: data === undefined ? {} : { "Content-Type": "application/json" },
    body: data === undefined ? undefined : JSON.stringify(data),
  });
  if (!response.ok) {
    if (response.status === 401 && !url.startsWith("/auth/"))
      window.dispatchEvent(new Event("session-expired"));
    const result = await response.json().catch(() => ({}));
    const detail =
      typeof result.detail === "string"
        ? result.detail
        : Array.isArray(result.detail)
          ? result.detail.map((v: { msg: string }) => v.msg).join("；")
          : "请求失败，请稍后重试";
    throw new Error(detail);
  }
  return response.json();
}
export type Note = {
  id: string;
  title: string;
  author: string;
  kind: string;
  cover: string | null;
  original_tags: string[];
  tags: string[];
  folder_ids: string[];
  has_ocr: boolean;
  created_at: number;
  updated_at: number;
  trashed_at: number | null;
  liked_count: number | string;
  image_count: number;
  media_missing: boolean;
};
export type NoteDetail = Note & {
  data: Record<string, string | number | string[]>;
  images: string[];
  video: string | null;
  ocr_text: string;
  files: { name: string; url: string }[];
};
export type Folder = {
  id: string;
  name: string;
  parent_id: string | null;
  count: number;
};
export type Overview = {
  total: number;
  images: number;
  videos: number;
  ocr: number;
  trash: number;
  folders: Folder[];
  tags: string[];
  original_tags: string[];
  xhs: { state: string; nickname?: string };
  running_jobs: number;
};
export type Job = {
  id: string;
  kind: string;
  title: string;
  state: string;
  message: string;
  total: number;
  done: number;
  counts: Record<string, number>;
  created_at: number;
  items?: { id: string; note_id: string; state: string; message: string }[];
};
export const states: Record<string, string> = {
  queued: "等待执行",
  running: "进行中",
  paused: "已暂停",
  waiting_login: "等待登录",
  cancelled: "已取消",
  failed: "需要处理",
  completed: "已完成",
};
export function date(value: number) {
  return new Date(value * 1000).toLocaleDateString("zh-CN", {
    month: "short",
    day: "numeric",
  });
}
export function compact(value: number | string) {
  const n = Number(value);
  return Number.isFinite(n)
    ? n >= 10000
      ? `${(n / 10000).toFixed(1)}万`
      : n >= 1000
        ? `${(n / 1000).toFixed(1)}k`
        : String(n)
    : value;
}
export function safeLink(value: unknown): string | undefined {
  try {
    const u = new URL(String(value));
    return ["http:", "https:"].includes(u.protocol) ? u.href : undefined;
  } catch {
    return undefined;
  }
}

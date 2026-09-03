import { useEffect, useState, type FormEvent } from "react";
import {
  CheckCircle2,
  Eye,
  LoaderCircle,
  Pencil,
  Plus,
  Sparkles,
  Trash2,
  X,
} from "lucide-react";
import { api } from "../api";
import type { AIModel } from "../chat";
import { Button } from "./ui/button";
import { Dialog } from "./ui/dialog";

const empty = { name: "", base_url: "", model: "", vision: true, key: "" };
export function AISettings({
  notify,
}: {
  notify: (text: string, error?: boolean) => void;
}) {
  const [models, setModels] = useState<AIModel[]>([]),
    [loaded, setLoaded] = useState(false);
  const [editing, setEditing] = useState<AIModel | "new" | null>(null),
    [form, setForm] = useState(empty);
  const [busy, setBusy] = useState(""),
    [remove, setRemove] = useState<AIModel | null>(null);
  const [tested, setTested] = useState("");
  useEffect(() => {
    api<AIModel[]>("/settings/ai/models")
      .then(setModels)
      .catch((e) => notify(e.message, true))
      .finally(() => setLoaded(true));
  }, [notify]);
  function edit(model: AIModel | "new") {
    setEditing(model);
    setForm(model === "new" ? empty : { ...model, key: "" });
    setTested("");
  }
  async function save(event: FormEvent) {
    event.preventDefault();
    setBusy("save");
    try {
      const value = await api<AIModel>(
        `/settings/ai/models${editing && editing !== "new" ? `/${editing.id}` : ""}`,
        { ...form, key: form.key || null },
        editing === "new" ? "POST" : "PUT",
      );
      setModels((items) =>
        items.some((m) => m.id === value.id)
          ? items.map((m) => (m.id === value.id ? value : m))
          : [...items, value],
      );
      setEditing(null);
      setForm(empty);
      notify("对话模型已保存");
    } catch (e) {
      notify((e as Error).message, true);
    } finally {
      setBusy("");
    }
  }
  async function test(model: AIModel) {
    setBusy(model.id);
    setTested("");
    try {
      await api(`/settings/ai/models/${model.id}/test`, {});
      setTested(model.id);
      notify(`${model.name} 文本连接测试通过`);
    } catch (e) {
      notify((e as Error).message, true);
    } finally {
      setBusy("");
    }
  }
  return (
    <section className="settings-card ai-settings" id="ai-model-settings">
      <div className="settings-heading">
        <span className="soft-icon">
          <Sparkles size={21} />
        </span>
        <div>
          <h2>AI 对话模型</h2>
          <p>添加自己的模型，在对话中自由切换。Key 加密保存在本机。</p>
        </div>
      </div>
      <div className="ai-model-list">
        {models.map((model) => (
          <div className="ai-model-row" key={model.id}>
            <span className="ai-model-icon">
              <Sparkles size={18} />
            </span>
            <div>
              <strong>{model.name}</strong>
              <span>
                {model.model} · {model.vision ? "图文理解" : "仅文本"}
              </span>
            </div>
            <div className="ai-model-actions">
              <Button
                size="sm"
                variant="ghost"
                disabled={!!busy}
                onClick={() => test(model)}
              >
                {busy === model.id ? (
                  <LoaderCircle className="spin" size={15} />
                ) : tested === model.id ? (
                  <CheckCircle2 size={15} />
                ) : null}
                测试连接
              </Button>
              <button
                aria-label={`编辑模型 ${model.name}`}
                onClick={() => edit(model)}
              >
                <Pencil size={16} />
              </button>
              <button
                aria-label={`删除模型 ${model.name}`}
                onClick={() => setRemove(model)}
              >
                <Trash2 size={16} />
              </button>
            </div>
          </div>
        ))}
        {loaded && !models.length && (
          <p className="ai-model-empty">
            还没有对话模型。添加后，就能带着素材与 AI 交流。
          </p>
        )}
      </div>
      {editing ? (
        <form className="ai-model-form" onSubmit={save}>
          <div className="ai-form-title">
            <h3>{editing === "new" ? "添加模型" : "编辑模型"}</h3>
            <button
              type="button"
              aria-label="取消编辑模型"
              onClick={() => setEditing(null)}
            >
              <X size={18} />
            </button>
          </div>
          <div className="form-two">
            <label>
              显示名称
              <input
                value={form.name}
                maxLength={100}
                required
                placeholder="例如：我的研究助手"
                onChange={(e) => setForm({ ...form, name: e.target.value })}
              />
            </label>
            <label>
              模型 ID
              <input
                value={form.model}
                maxLength={200}
                required
                placeholder="填写服务商提供的模型 ID"
                onChange={(e) => setForm({ ...form, model: e.target.value })}
              />
            </label>
          </div>
          <label>
            API Base URL
            <input
              type="url"
              required
              value={form.base_url}
              placeholder="https://你的模型服务/v1"
              onChange={(e) => setForm({ ...form, base_url: e.target.value })}
            />
            <small>
              支持兼容 Chat Completions 的服务，也可填写本机模型服务地址。
            </small>
          </label>
          <label>
            API Key
            <input
              type="password"
              autoComplete="new-password"
              value={form.key}
              placeholder={
                editing !== "new" && editing.has_key
                  ? "已配置 · 留空保留现有 Key"
                  : "填写 API Key；本机免密服务可留空"
              }
              onChange={(e) => setForm({ ...form, key: e.target.value })}
            />
          </label>
          <label className="ai-vision-check">
            <input
              type="checkbox"
              checked={form.vision}
              onChange={(e) => setForm({ ...form, vision: e.target.checked })}
            />
            <span>
              <strong>
                <Eye size={15} />
                模型支持图片理解
              </strong>
              <small>
                开启后发送图片及视频抽样画面。仅文本模型请关闭；OCR
                文字始终可用。
              </small>
            </span>
          </label>
          <div className="dialog-actions">
            <Button
              type="button"
              variant="ghost"
              onClick={() => setEditing(null)}
            >
              取消
            </Button>
            <Button type="submit" disabled={!!busy}>
              {busy === "save" && <LoaderCircle size={15} className="spin" />}
              保存模型
            </Button>
          </div>
        </form>
      ) : (
        <Button variant="secondary" onClick={() => edit("new")}>
          <Plus size={16} />
          添加模型
        </Button>
      )}
      <Dialog
        open={!!remove}
        onOpenChange={(open) => !open && setRemove(null)}
        title="删除这个模型？"
        description="对话记录和素材会保留；此模型的本地 Key 将一并删除。"
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
                await api(
                  `/settings/ai/models/${remove.id}`,
                  undefined,
                  "DELETE",
                );
                setModels((items) => items.filter((m) => m.id !== remove.id));
                setRemove(null);
              } catch (e) {
                notify((e as Error).message, true);
              }
            }}
          >
            删除模型
          </Button>
        </div>
      </Dialog>
    </section>
  );
}

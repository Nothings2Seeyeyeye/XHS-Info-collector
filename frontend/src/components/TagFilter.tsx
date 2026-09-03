import { useMemo, useState } from "react";
import { Check, ChevronDown, Search, Tags } from "lucide-react";
import { Dialog } from "./ui/dialog";

export function TagFilter({
  value,
  onChange,
  originals,
  personal,
}: {
  value: string;
  onChange: (value: string) => void;
  originals: string[];
  personal: string[];
}) {
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState("");
  const [source, setSource] = useState<"raw" | "my">("raw");
  const visible = useMemo(
    () =>
      (source === "raw" ? originals : personal).filter((tag) =>
        tag.toLocaleLowerCase().includes(query.toLocaleLowerCase()),
      ),
    [source, query, originals, personal],
  );
  function choose(tag: string) {
    onChange(tag);
    setOpen(false);
    setQuery("");
  }
  return (
    <>
      <button
        className={`filter-trigger ${value ? "has-value" : ""}`}
        aria-label="标签筛选"
        aria-haspopup="dialog"
        onClick={() => setOpen(true)}
      >
        <Tags size={16} />
        <span>{value ? value.slice(value.indexOf(":") + 1) : "全部标签"}</span>
        <ChevronDown size={14} />
      </button>
      <Dialog
        open={open}
        onOpenChange={setOpen}
        title="找到那一类灵感"
        description="按笔记原始标签或你的个人标签，快速筛选素材。"
        className="tag-filter-dialog"
      >
        <label className="tag-search">
          <Search size={18} />
          <input
            aria-label="查找标签"
            autoFocus
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="输入标签名称…"
          />
        </label>
        <div className="segmented tag-sources" aria-label="标签来源">
          <button
            className={source === "raw" ? "active" : ""}
            onClick={() => setSource("raw")}
          >
            原始标签 <small>{originals.length}</small>
          </button>
          <button
            className={source === "my" ? "active" : ""}
            onClick={() => setSource("my")}
          >
            我的标签 <small>{personal.length}</small>
          </button>
        </div>
        <div className="tag-options">
          <button
            className={!value ? "selected" : ""}
            onClick={() => choose("")}
          >
            全部标签 {!value && <Check size={14} />}
          </button>
          {visible.map((tag) => (
            <button
              key={tag}
              className={value === `${source}:${tag}` ? "selected" : ""}
              onClick={() => choose(`${source}:${tag}`)}
            >
              <span># {tag}</span>
              {value === `${source}:${tag}` && <Check size={14} />}
            </button>
          ))}
          {!visible.length && (
            <p className="tag-empty">
              {query
                ? "没有匹配的标签，试试其他关键词。"
                : "还没有个人标签，可在笔记详情中添加。"}
            </p>
          )}
        </div>
      </Dialog>
    </>
  );
}

export type AIModel = {
  id: string;
  name: string;
  base_url: string;
  model: string;
  vision: boolean;
  has_key: boolean;
};
export type ChatSource = {
  id: string;
  title: string;
  author: string;
  kind: string;
  cover: string | null;
  has_ocr: boolean;
  image_count: number;
  coverage?: string;
};
export type ChatMessage = {
  id: string;
  thread_id: string;
  role: "user" | "assistant";
  content: string;
  sources: ChatSource[];
  status: string;
  error: string;
  model_name: string;
  reply_to: string;
  created_at: number;
};
export type ChatThread = {
  id: string;
  title: string;
  source_ids: string[];
  model_id: string;
  created_at: number;
  updated_at: number;
};
export type ChatDetail = ChatThread & { messages: ChatMessage[] };
export const isGenerating = (message: ChatMessage) =>
  ["pending", "generating"].includes(message.status);

/**
 * API 客户端
 *
 * 统一封装后端接口调用，其他页面只用这个文件
 */

import { toast } from "@/components/Toast";

const API_BASE = "http://127.0.0.1:8000/api/v1";

// 从 localStorage 拿 token
function getToken(): string | null {
  if (typeof window === "undefined") return null;
  return localStorage.getItem("token");
}

// 通用请求方法
async function request<T>(
  path: string,
  options: RequestInit = {}
): Promise<T> {
  const token = getToken();
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    ...((options.headers as Record<string, string>) || {}),
  };

  if (token) {
    headers["Authorization"] = `Bearer ${token}`;
  }

  const res = await fetch(`${API_BASE}${path}`, {
    ...options,
    headers,
  });

  if (!res.ok) {
    const error = await res.json().catch(() => ({ detail: "请求失败" }));
    const msg = error.detail || "请求失败";
    toast(msg);
    throw new Error(msg);
  }

  return res.json();
}

// ========== 租户接口 ==========

export async function register(name: string, email: string, password: string) {
  return request<{
    id: string;
    name: string;
    email: string;
    api_key: string;
    plan: string;
  }>("/tenants/register", {
    method: "POST",
    body: JSON.stringify({ name, email, password }),
  });
}

export async function login(email: string, password: string) {
  return request<{ access_token: string }>("/tenants/login", {
    method: "POST",
    body: JSON.stringify({ email, password }),
  });
}

export async function getMe() {
  return request<{
    id: string;
    name: string;
    email: string;
    api_key: string;
    plan: string;
  }>("/tenants/me");
}

// ========== 文档接口 ==========

export async function uploadDocument(file: File) {
  const token = getToken();
  const formData = new FormData();
  formData.append("file", file);

  const res = await fetch(`${API_BASE}/documents/upload`, {
    method: "POST",
    headers: {
      Authorization: `Bearer ${token}`,
    },
    body: formData,
  });

  if (!res.ok) {
    const error = await res.json().catch(() => ({ detail: "上传失败" }));
    const msg = error.detail || "上传失败";
    toast(msg);
    throw new Error(msg);
  }

  return res.json();
}

export async function listDocuments() {
  return request<{ documents: any[]; total: number }>("/documents/");
}

export async function deleteDocument(documentId: string) {
  return request<{ detail: string }>(`/documents/${documentId}`, {
    method: "DELETE",
  });
}

export async function getDocumentChunks(documentId: string) {
  return request<{ chunks: any[]; total: number }>(`/documents/${documentId}/chunks`);
}

export async function getChunksByIds(chunkIds: string[]) {
  return request<{ chunks: Record<string, string> }>("/documents/chunks/by-ids", {
    method: "POST",
    body: JSON.stringify({ chunk_ids: chunkIds }),
  });
}

// ========== 对话接口 ==========

export async function ask(question: string, sessionId?: string) {
  return request<{
    answer: string;
    session_id: string;
    retrieved_chunks: string[];
    retrieved_scores: number[];
  }>("/conversations/ask", {
    method: "POST",
    body: JSON.stringify({ question, session_id: sessionId }),
  });
}

export async function listSessions() {
  return request<{ sessions: any[]; total: number }>("/conversations/sessions");
}

export async function getSessionMessages(sessionId: string) {
  return request<{ messages: any[]; total: number }>(`/conversations/sessions/${sessionId}`);
}

// ========== 评估接口 ==========

export async function generateGoldenSet(numChunks: number = 10) {
  return request<{
    file_path: string;
    question_count: number;
    message: string;
  }>("/eval/generate-golden-set", {
    method: "POST",
    body: JSON.stringify({ num_chunks: numChunks }),
  });
}

export async function listGoldenSets() {
  return request<{ golden_sets: any[]; total: number }>("/eval/golden-sets");
}

export async function getGoldenSet(filename: string) {
  return request<{ filename: string; items: any[] }>(`/eval/golden-sets/${filename}`);
}

export async function runEvaluation(
  goldenSetPath: string,
  topK: number = 3,
  mode: string = "quick"
) {
  return request<{
    mode: string;
    total_questions: number;
    avg_recall_at_k: number;
    avg_mrr: number;
    avg_faithfulness?: number;
    avg_relevance?: number;
    details: any[];
  }>("/eval/run-evaluation", {
    method: "POST",
    body: JSON.stringify({
      golden_set_path: goldenSetPath,
      top_k: topK,
      mode,
    }),
  });
}

// ========== 工具配置接口 ==========

export interface ToolConfig {
  id: string;
  tenant_id: string;
  name: string;
  description: string;
  parameters: Record<string, any>;
  endpoint: string;
  method: string;
  auth_type: string;
  is_active: boolean;
  created_at: string;
}

export interface ToolConfigCreate {
  name: string;
  description: string;
  parameters?: Record<string, any>;
  endpoint: string;
  method?: string;
  auth_type?: string;
  auth_config?: Record<string, any>;
}

export async function listTools() {
  return request<{ tools: ToolConfig[]; total: number }>("/tools/");
}

export async function createTool(data: ToolConfigCreate) {
  return request<ToolConfig>("/tools/", {
    method: "POST",
    body: JSON.stringify(data),
  });
}

export async function updateTool(toolId: string, data: Partial<ToolConfigCreate & { is_active: boolean }>) {
  return request<ToolConfig>(`/tools/${toolId}`, {
    method: "PUT",
    body: JSON.stringify(data),
  });
}

export async function deleteTool(toolId: string) {
  return request<{ detail: string }>(`/tools/${toolId}`, {
    method: "DELETE",
  });
}

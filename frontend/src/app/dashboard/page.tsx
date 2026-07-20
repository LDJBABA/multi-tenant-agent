"use client";

import { useState, useEffect, useRef, Fragment } from "react";
import { useRouter } from "next/navigation";
import { getMe, uploadDocument, listDocuments, ask, deleteDocument, getDocumentChunks, listSessions, getSessionMessages, generateGoldenSet, listGoldenSets, runEvaluation, getChunksByIds, listTools, createTool, updateTool, deleteTool, type ToolConfig } from "@/lib/api";
import { toast } from "@/components/Toast";

// Chunk ID 悬浮提示组件
function ChunkIdBadge({ chunkId, cache, onFetch }: {
  chunkId: string;
  cache: Record<string, string>;
  onFetch: (id: string) => void;
}) {
  const [show, setShow] = useState(false);
  const [pos, setPos] = useState({ x: 0, y: 0 });

  return (
    <span
      className="inline-block relative cursor-pointer text-blue-600 hover:underline"
      onMouseEnter={(e) => {
        onFetch(chunkId);
        setPos({ x: e.clientX, y: e.clientY });
        setShow(true);
      }}
      onMouseLeave={() => setShow(false)}
    >
      {chunkId}
      {show && (
        <div
          className="fixed z-50 w-80 p-3 bg-gray-800 text-white text-xs rounded shadow-lg whitespace-normal break-words"
          style={{ left: pos.x + 10, top: pos.y + 10 }}
        >
          {cache[chunkId] || "加载中..."}
        </div>
      )}
    </span>
  );
}

interface Document {
  id: string;
  filename: string;
  status: string;
  chunk_count: number;
  created_at: string;
}

interface Chunk {
  id: string;
  chunk_index: number;
  content: string;
  token_count: number;
}

interface Session {
  id: string;
  created_at: string;
}

interface ChatMessage {
  role: "user" | "assistant";
  content: string;
  chunks?: string[];
  scores?: number[];
}

export default function DashboardPage() {
  const router = useRouter();
  const [tenant, setTenant] = useState<any>(null);
  const [documents, setDocuments] = useState<Document[]>([]);
  const [uploading, setUploading] = useState(false);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [question, setQuestion] = useState("");
  const [asking, setAsking] = useState(false);
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState<"upload" | "chat" | "eval" | "tools">("upload");
  const chatEndRef = useRef<HTMLDivElement>(null);
  const [expandedDocId, setExpandedDocId] = useState<string | null>(null);
  const [docChunks, setDocChunks] = useState<Chunk[]>([]);
  const [loadingChunks, setLoadingChunks] = useState(false);
  const [sessions, setSessions] = useState<Session[]>([]);
  const [activeSessionId, setActiveSessionId] = useState<string | null>(null);

  // 评估相关状态
  const [evalTab, setEvalTab] = useState<"generate" | "run" | "report">("generate");
  const [goldenSets, setGoldenSets] = useState<any[]>([]);
  const [selectedGoldenSet, setSelectedGoldenSet] = useState<string>("");
  const [numChunks, setNumChunks] = useState(10);
  const [topK, setTopK] = useState(3);
  const [evalMode, setEvalMode] = useState<"quick" | "full">("quick");
  const [generating, setGenerating] = useState(false);
  const [evaluating, setEvaluating] = useState(false);
  const [evalReport, setEvalReport] = useState<any>(null);
  const [expandedQuery, setExpandedQuery] = useState<number | null>(null);
  const [chunkContentCache, setChunkContentCache] = useState<Record<string, string>>({});

  // 工具管理相关状态
  const [tools, setTools] = useState<ToolConfig[]>([]);
  const [showToolForm, setShowToolForm] = useState(false);
  const [editingTool, setEditingTool] = useState<ToolConfig | null>(null);
  const [toolForm, setToolForm] = useState({ name: "", description: "", endpoint: "", method: "POST", auth_type: "none" });

  // 加载租户信息和文档列表
  useEffect(() => {
    const token = localStorage.getItem("token");
    if (!token) {
      router.push("/login");
      return;
    }

    getMe()
      .then(setTenant)
      .catch(() => router.push("/login"));

    listDocuments().then((data) => setDocuments(data.documents));
  }, [router]);

  // 自动滚动到底部
  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  // 加载会话列表
  useEffect(() => {
    if (activeTab === "chat") {
      listSessions().then((data) => setSessions(data.sessions));
    }
  }, [activeTab]);

  // 加载黄金集列表
  useEffect(() => {
    if (activeTab === "eval") {
      listGoldenSets().then((data) => setGoldenSets(data.golden_sets));
    }
  }, [activeTab]);

  // 加载工具列表
  useEffect(() => {
    if (activeTab === "tools") {
      listTools().then((data) => setTools(data.tools));
    }
  }, [activeTab]);

  // 上传文件
  const handleUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;

    setUploading(true);
    try {
      const doc = await uploadDocument(file);
      setDocuments((prev) => [doc, ...prev]);
      toast(`上传成功！已切分为 ${doc.chunk_count} 个片段`, "success");
    } catch (err: any) {
      // toast 已在 api.ts 里统一处理
    } finally {
      setUploading(false);
      e.target.value = "";
    }
  };

  // 提问
  const handleAsk = async () => {
    if (!question.trim() || asking) return;

    const userMsg: ChatMessage = { role: "user", content: question };
    setMessages((prev) => [...prev, userMsg]);
    setQuestion("");
    setAsking(true);

    try {
      const result = await ask(question, sessionId || undefined);
      setSessionId(result.session_id);
      const aiMsg: ChatMessage = {
        role: "assistant",
        content: result.answer,
        chunks: result.retrieved_chunks,
        scores: result.retrieved_scores,
      };
      setMessages((prev) => [...prev, aiMsg]);
    } catch (err: any) {
      const errMsg: ChatMessage = {
        role: "assistant",
        content: `错误：${err.message}`,
      };
      setMessages((prev) => [...prev, errMsg]);
    } finally {
      setAsking(false);
    }
  };

  // 查看文档 chunks
  const handleViewChunks = async (docId: string) => {
    if (expandedDocId === docId) {
      setExpandedDocId(null);
      setDocChunks([]);
      return;
    }

    setLoadingChunks(true);
    setExpandedDocId(docId);
    try {
      const data = await getDocumentChunks(docId);
      setDocChunks(data.chunks);
    } catch (err: any) {
      toast(err.message || "获取片段失败");
      setExpandedDocId(null);
    } finally {
      setLoadingChunks(false);
    }
  };

  // 加载历史会话
  const handleLoadSession = async (sessId: string) => {
    try {
      const data = await getSessionMessages(sessId);
      const loadedMessages: ChatMessage[] = data.messages.map((msg) => ({
        role: msg.role,
        content: msg.content,
      }));
      setMessages(loadedMessages);
      setSessionId(sessId);
      setActiveSessionId(sessId);
    } catch (err: any) {
      toast(err.message || "加载会话失败");
    }
  };

  // 新建会话
  const handleNewSession = () => {
    setMessages([]);
    setSessionId(null);
    setActiveSessionId(null);
  };

  // 删除文档
  const handleDelete = async (docId: string, filename: string) => {
    if (!confirm(`确认删除文档 "${filename}"？`)) return;
    try {
      await deleteDocument(docId);
      setDocuments((prev) => prev.filter((d) => d.id !== docId));
      toast("删除成功", "success");
    } catch (err: any) {
      // toast 已在 api.ts 里统一处理
    }
  };

  // 登出
  const handleLogout = () => {
    localStorage.removeItem("token");
    router.push("/login");
  };

  // 获取 chunk 内容（带缓存）
  const fetchChunkContent = async (chunkId: string) => {
    if (chunkContentCache[chunkId]) return;
    try {
      const data = await getChunksByIds([chunkId]);
      setChunkContentCache((prev) => ({ ...prev, ...data.chunks }));
    } catch {
      // 静默失败
    }
  };

  // 生成黄金集
  const handleGenerateGoldenSet = async () => {
    setGenerating(true);
    try {
      const result = await generateGoldenSet(numChunks);
      toast(`黄金集已生成，共 ${result.question_count} 个问题`, "success");
      // 刷新列表
      const data = await listGoldenSets();
      setGoldenSets(data.golden_sets);
      setEvalTab("run");
    } catch (err: any) {
      // toast 已在 api.ts 里统一处理
    } finally {
      setGenerating(false);
    }
  };

  // 执行评估
  const handleRunEvaluation = async () => {
    if (!selectedGoldenSet) {
      toast("请先选择黄金集");
      return;
    }
    setEvaluating(true);
    try {
      const report = await runEvaluation(selectedGoldenSet, topK, evalMode);
      setEvalReport(report);
      setEvalTab("report");
      toast("评估完成", "success");
    } catch (err: any) {
      // toast 已在 api.ts 里统一处理
    } finally {
      setEvaluating(false);
    }
  };

  // 工具管理
  const handleSaveTool = async () => {
    try {
      if (editingTool) {
        await updateTool(editingTool.id, toolForm);
        toast("工具更新成功", "success");
      } else {
        await createTool(toolForm);
        toast("工具创建成功", "success");
      }
      setShowToolForm(false);
      setEditingTool(null);
      setToolForm({ name: "", description: "", endpoint: "", method: "POST", auth_type: "none" });
      const data = await listTools();
      setTools(data.tools);
    } catch (err: any) {
      // toast 已在 api.ts 里统一处理
    }
  };

  const handleDeleteTool = async (toolId: string) => {
    if (!confirm("确认删除该工具？")) return;
    try {
      await deleteTool(toolId);
      toast("删除成功", "success");
      setTools((prev) => prev.filter((t) => t.id !== toolId));
    } catch (err: any) {
      // toast 已在 api.ts 里统一处理
    }
  };

  const handleToggleTool = async (tool: ToolConfig) => {
    try {
      await updateTool(tool.id, { is_active: !tool.is_active });
      setTools((prev) => prev.map((t) => t.id === tool.id ? { ...t, is_active: !t.is_active } : t));
    } catch (err: any) {
      // toast 已在 api.ts 里统一处理
    }
  };

  const handleEditTool = (tool: ToolConfig) => {
    setEditingTool(tool);
    setToolForm({ name: tool.name, description: tool.description, endpoint: tool.endpoint, method: tool.method, auth_type: tool.auth_type });
    setShowToolForm(true);
  };

  if (!tenant) return null;

  return (
    <div className="min-h-screen bg-gray-50">
      {/* 顶部导航 */}
      <header className="bg-white shadow">
        <div className="max-w-7xl mx-auto px-4 py-3 flex justify-between items-center">
          <h1 className="text-xl font-bold">智能客服控制台</h1>
          <div className="flex items-center gap-4">
            <span className="text-sm text-gray-500">{tenant.name}</span>
            <button
              onClick={handleLogout}
              className="text-sm text-red-600 hover:underline"
            >
              登出
            </button>
          </div>
        </div>
      </header>

      <div className="max-w-7xl mx-auto px-4 py-6">
        {/* Tab 切换 */}
        <div className="flex gap-4 mb-6">
          <button
            onClick={() => setActiveTab("upload")}
            className={`px-4 py-2 rounded-lg ${
              activeTab === "upload"
                ? "bg-blue-600 text-white"
                : "bg-white text-gray-700 border"
            }`}
          >
            文档管理
          </button>
          <button
            onClick={() => setActiveTab("chat")}
            className={`px-4 py-2 rounded-lg ${
              activeTab === "chat"
                ? "bg-blue-600 text-white"
                : "bg-white text-gray-700 border"
            }`}
          >
            对话测试
          </button>
          <button
            onClick={() => setActiveTab("eval")}
            className={`px-4 py-2 rounded-lg ${
              activeTab === "eval"
                ? "bg-blue-600 text-white"
                : "bg-white text-gray-700 border"
            }`}
          >
            评估
          </button>
          <button
            onClick={() => setActiveTab("tools")}
            className={`px-4 py-2 rounded-lg ${
              activeTab === "tools"
                ? "bg-blue-600 text-white"
                : "bg-white text-gray-700 border"
            }`}
          >
            工具管理
          </button>
        </div>

        {/* 文档管理 */}
        {activeTab === "upload" && (
          <div className="bg-white rounded-lg shadow p-6">
            <h2 className="text-lg font-semibold mb-4">上传知识库文档</h2>

            <label className="block w-full p-8 border-2 border-dashed rounded-lg text-center cursor-pointer hover:border-blue-400">
              <input
                type="file"
                accept=".pdf,.txt,.md,.docx"
                onChange={handleUpload}
                className="hidden"
                disabled={uploading}
              />
              {uploading ? (
                <span className="text-gray-500">上传中...</span>
              ) : (
                <span className="text-gray-500">
                  点击选择文件（支持 PDF / TXT / MD / DOCX）
                </span>
              )}
            </label>

            <h3 className="text-md font-semibold mt-6 mb-3">已上传文档</h3>
            {documents.length === 0 ? (
              <p className="text-gray-400 text-sm">暂无文档</p>
            ) : (
              <table className="w-full text-sm">
                <thead>
                  <tr className="text-left text-gray-500 border-b">
                    <th className="py-2">文件名</th>
                    <th>状态</th>
                    <th>片段数</th>
                    <th>上传时间</th>
                    <th>操作</th>
                  </tr>
                </thead>
                <tbody>
                  {documents.map((doc) => (
                    <Fragment key={doc.id}>
                      <tr className="border-b">
                        <td className="py-2">{doc.filename}</td>
                        <td>
                          <span
                            className={`px-2 py-0.5 rounded text-xs ${
                              doc.status === "ready"
                                ? "bg-green-100 text-green-700"
                                : doc.status === "failed"
                                ? "bg-red-100 text-red-700"
                                : "bg-yellow-100 text-yellow-700"
                            }`}
                          >
                            {doc.status}
                          </span>
                        </td>
                        <td>
                          <button
                            onClick={() => handleViewChunks(doc.id)}
                            className="text-blue-600 hover:underline"
                            disabled={doc.chunk_count === 0}
                          >
                            {doc.chunk_count}
                          </button>
                        </td>
                        <td>{new Date(doc.created_at).toLocaleString()}</td>
                        <td>
                          <button
                            onClick={() => handleDelete(doc.id, doc.filename)}
                            className="text-red-600 hover:underline text-xs"
                          >
                            删除
                          </button>
                        </td>
                      </tr>
                      {expandedDocId === doc.id && (
                        <tr>
                          <td colSpan={5} className="p-4 bg-gray-50">
                            {loadingChunks ? (
                              <p className="text-gray-400 text-sm">加载中...</p>
                            ) : docChunks.length === 0 ? (
                              <p className="text-gray-400 text-sm">暂无片段</p>
                            ) : (
                              <div className="space-y-2 max-h-60 overflow-y-auto">
                                {docChunks.map((chunk) => (
                                  <div key={chunk.id} className="p-3 bg-white rounded border text-xs">
                                    <div className="flex justify-between text-gray-400 mb-1">
                                      <span>片段 {chunk.chunk_index}</span>
                                      <span>{chunk.token_count} tokens</span>
                                    </div>
                                    <p className="text-gray-700">{chunk.content}</p>
                                  </div>
                                ))}
                              </div>
                            )}
                          </td>
                        </tr>
                      )}
                    </Fragment>
                  ))}
                </tbody>
              </table>
            )}
          </div>
        )}

        {/* 对话测试 */}
        {activeTab === "chat" && (
          <div className="flex gap-4 h-[600px]">
            {/* 左侧：历史会话列表 */}
            <div className="w-64 bg-white rounded-lg shadow overflow-hidden flex flex-col">
              <div className="p-3 border-b flex justify-between items-center">
                <h3 className="text-sm font-semibold">历史会话</h3>
                <button
                  onClick={handleNewSession}
                  className="text-xs text-blue-600 hover:underline"
                >
                  新建
                </button>
              </div>
              <div className="flex-1 overflow-y-auto">
                {sessions.length === 0 ? (
                  <p className="text-xs text-gray-400 p-3">暂无会话</p>
                ) : (
                  sessions.map((sess) => (
                    <div
                      key={sess.id}
                      onClick={() => handleLoadSession(sess.id)}
                      className={`p-3 text-xs cursor-pointer hover:bg-gray-50 border-b ${
                        activeSessionId === sess.id ? "bg-blue-50" : ""
                      }`}
                    >
                      <p className="text-gray-500">
                        {new Date(sess.created_at).toLocaleString()}
                      </p>
                      <p className="text-gray-400 mt-1 truncate">
                        {sess.id.slice(0, 8)}...
                      </p>
                    </div>
                  ))
                )}
              </div>
            </div>

            {/* 右侧：对话区域 */}
            <div className="flex-1 bg-white rounded-lg shadow flex flex-col">
              <div className="p-4 border-b">
                <h2 className="text-lg font-semibold">对话测试</h2>
                <p className="text-xs text-gray-400">
                  基于已上传的知识库内容回答
                </p>
              </div>

              {/* 消息列表 */}
              <div className="flex-1 overflow-y-auto p-4 space-y-4">
                {messages.length === 0 && (
                  <p className="text-center text-gray-400 mt-20">
                    上传文档后，在这里提问测试
                  </p>
                )}
                {messages.map((msg, i) => (
                  <div
                    key={i}
                    className={`flex ${
                      msg.role === "user" ? "justify-end" : "justify-start"
                    }`}
                  >
                    <div
                      className={`max-w-[70%] p-3 rounded-lg ${
                        msg.role === "user"
                          ? "bg-blue-600 text-white"
                          : "bg-gray-100 text-gray-800"
                      }`}
                    >
                      <p className="whitespace-pre-wrap">{msg.content}</p>
                      {msg.chunks && msg.chunks.length > 0 && (
                        <details className="mt-2 text-xs">
                          <summary className="cursor-pointer opacity-70">
                            查看检索到的内容
                          </summary>
                          {msg.chunks.map((chunk, j) => (
                            <div key={j} className="mt-1 p-2 bg-white/20 rounded">
                              <div className="flex justify-between mb-1">
                                <span className="text-gray-500">片段 {j + 1}</span>
                                {msg.scores && (
                                  <span className="text-gray-400">
                                    相似度: {(msg.scores[j] * 100).toFixed(1)}%
                                  </span>
                                )}
                              </div>
                              <p>{chunk}</p>
                            </div>
                          ))}
                        </details>
                      )}
                    </div>
                  </div>
                ))}
                {asking && (
                  <div className="flex justify-start">
                    <div className="bg-gray-100 p-3 rounded-lg">
                      <span className="animate-pulse">思考中...</span>
                    </div>
                  </div>
                )}
                <div ref={chatEndRef} />
              </div>

              {/* 输入框 */}
              <div className="p-4 border-t flex gap-2">
                <input
                  type="text"
                  value={question}
                  onChange={(e) => setQuestion(e.target.value)}
                  onKeyDown={(e) => e.key === "Enter" && handleAsk()}
                  placeholder="输入问题..."
                  className="flex-1 px-4 py-2 border rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
                  disabled={asking}
                />
                <button
                  onClick={handleAsk}
                  disabled={asking || !question.trim()}
                  className="px-6 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50"
                >
                  发送
                </button>
              </div>
            </div>
          </div>
        )}

        {/* 评估 */}
        {activeTab === "eval" && (
          <div className="space-y-6">
            {/* 步骤导航 */}
            <div className="flex gap-4">
              <button
                onClick={() => setEvalTab("generate")}
                className={`px-4 py-2 rounded-lg ${
                  evalTab === "generate"
                    ? "bg-blue-600 text-white"
                    : "bg-white text-gray-700 border"
                }`}
              >
                ① 生成黄金集
              </button>
              <button
                onClick={() => setEvalTab("run")}
                className={`px-4 py-2 rounded-lg ${
                  evalTab === "run"
                    ? "bg-blue-600 text-white"
                    : "bg-white text-gray-700 border"
                }`}
              >
                ② 执行评估
              </button>
              <button
                onClick={() => setEvalTab("report")}
                className={`px-4 py-2 rounded-lg ${
                  evalTab === "report"
                    ? "bg-blue-600 text-white"
                    : "bg-white text-gray-700 border"
                }`}
              >
                ③ 查看报告
              </button>
            </div>

            {/* Step 1: 生成黄金集 */}
            {evalTab === "generate" && (
              <div className="bg-white rounded-lg shadow p-6">
                <h2 className="text-lg font-semibold mb-4">生成黄金集</h2>
                <p className="text-sm text-gray-500 mb-4">
                  从知识库 chunk 自动生成测试问题，每个问题对应多个 chunk
                </p>
                <div className="flex items-center gap-4">
                  <label className="text-sm">Chunk 数量：</label>
                  <input
                    type="number"
                    value={numChunks}
                    onChange={(e) => setNumChunks(Number(e.target.value))}
                    className="w-20 px-3 py-2 border rounded-lg"
                    min={1}
                    max={50}
                  />
                  <button
                    onClick={handleGenerateGoldenSet}
                    disabled={generating}
                    className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50"
                  >
                    {generating ? "生成中..." : "生成黄金集"}
                  </button>
                </div>
              </div>
            )}

            {/* Step 2: 执行评估 */}
            {evalTab === "run" && (
              <div className="bg-white rounded-lg shadow p-6">
                <h2 className="text-lg font-semibold mb-4">执行评估</h2>
                <div className="space-y-4">
                  <div>
                    <label className="text-sm">选择黄金集：</label>
                    <select
                      value={selectedGoldenSet}
                      onChange={(e) => setSelectedGoldenSet(e.target.value)}
                      className="ml-2 px-3 py-2 border rounded-lg"
                    >
                      <option value="">请选择</option>
                      {goldenSets.map((gs) => (
                        <option key={gs.filename} value={gs.path}>
                          {gs.filename} ({gs.question_count} 个问题)
                        </option>
                      ))}
                    </select>
                  </div>
                  <div className="flex items-center gap-4">
                    <label className="text-sm">Top-K：</label>
                    <input
                      type="number"
                      value={topK}
                      onChange={(e) => setTopK(Number(e.target.value))}
                      className="w-20 px-3 py-2 border rounded-lg"
                      min={1}
                      max={10}
                    />
                  </div>
                  <div className="flex items-center gap-4">
                    <label className="text-sm">评估模式：</label>
                    <select
                      value={evalMode}
                      onChange={(e) => setEvalMode(e.target.value as "quick" | "full")}
                      className="px-3 py-2 border rounded-lg"
                    >
                      <option value="quick">快速模式（只评估召回率）</option>
                      <option value="full">完整模式（评估召回率+回答质量）</option>
                    </select>
                  </div>
                  <button
                    onClick={handleRunEvaluation}
                    disabled={evaluating || !selectedGoldenSet}
                    className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50"
                  >
                    {evaluating ? "评估中..." : "开始评估"}
                  </button>
                </div>
              </div>
            )}

            {/* Step 3: 查看报告 */}
            {evalTab === "report" && evalReport && (
              <div className="space-y-6">
                {/* 汇总卡片 */}
                <div className="grid grid-cols-4 gap-4">
                  <div className="bg-white rounded-lg shadow p-4 text-center">
                    <p className="text-sm text-gray-500">Recall@K</p>
                    <p className="text-2xl font-bold text-blue-600">
                      {(evalReport.avg_recall_at_k * 100).toFixed(1)}%
                    </p>
                  </div>
                  <div className="bg-white rounded-lg shadow p-4 text-center">
                    <p className="text-sm text-gray-500">MRR</p>
                    <p className="text-2xl font-bold text-green-600">
                      {(evalReport.avg_mrr * 100).toFixed(1)}%
                    </p>
                  </div>
                  {evalReport.mode === "full" && (
                    <>
                      <div className="bg-white rounded-lg shadow p-4 text-center">
                        <p className="text-sm text-gray-500">Faithfulness</p>
                        <p className="text-2xl font-bold text-purple-600">
                          {((evalReport.avg_faithfulness || 0) * 100).toFixed(1)}%
                        </p>
                      </div>
                      <div className="bg-white rounded-lg shadow p-4 text-center">
                        <p className="text-sm text-gray-500">Relevance</p>
                        <p className="text-2xl font-bold text-orange-600">
                          {((evalReport.avg_relevance || 0) * 100).toFixed(1)}%
                        </p>
                      </div>
                    </>
                  )}
                </div>

                {/* 明细表格 */}
                <div className="bg-white rounded-lg shadow p-6">
                  <h3 className="text-md font-semibold mb-4">
                    问题详情（共 {evalReport.total_questions} 个）
                  </h3>
                  <table className="w-full text-sm">
                    <thead>
                      <tr className="text-left text-gray-500 border-b">
                        <th className="py-2">问题</th>
                        <th>Recall@K</th>
                        <th>MRR</th>
                        {evalReport.mode === "full" && (
                          <>
                            <th>Faithfulness</th>
                            <th>Relevance</th>
                          </>
                        )}
                      </tr>
                    </thead>
                    <tbody>
                      {evalReport.details.map((item: any, i: number) => (
                        <Fragment key={i}>
                          <tr
                            className="border-b cursor-pointer hover:bg-gray-50"
                            onClick={() =>
                              setExpandedQuery(expandedQuery === i ? null : i)
                            }
                          >
                            <td className="py-2">{item.query}</td>
                            <td>
                              <span
                                className={`px-2 py-0.5 rounded text-xs ${
                                  item.recall_at_k >= 1
                                    ? "bg-green-100 text-green-700"
                                    : "bg-red-100 text-red-700"
                                }`}
                              >
                                {(item.recall_at_k * 100).toFixed(0)}%
                              </span>
                            </td>
                            <td>{(item.mrr * 100).toFixed(0)}%</td>
                            {evalReport.mode === "full" && (
                              <>
                                <td>{((item.faithfulness || 0) * 100).toFixed(0)}%</td>
                                <td>{((item.relevance || 0) * 100).toFixed(0)}%</td>
                              </>
                            )}
                          </tr>
                          {expandedQuery === i && (
                            <tr>
                              <td
                                colSpan={evalReport.mode === "full" ? 5 : 3}
                                className="p-4 bg-gray-50"
                              >
                                <div className="space-y-3">
                                  <div>
                                    <p className="text-xs text-gray-500 mb-1">
                                      期望的 Chunk IDs：
                                    </p>
                                    <div className="text-xs flex flex-wrap gap-1">
                                      {item.expected_chunk_ids.map((cid: string, idx: number) => (
                                        <Fragment key={idx}>
                                          <ChunkIdBadge chunkId={cid} cache={chunkContentCache} onFetch={fetchChunkContent} />
                                          {idx < item.expected_chunk_ids.length - 1 && <span>,</span>}
                                        </Fragment>
                                      ))}
                                    </div>
                                  </div>
                                  <div>
                                    <p className="text-xs text-gray-500 mb-1">
                                      检索到的 Chunk IDs：
                                    </p>
                                    <div className="text-xs flex flex-wrap gap-1">
                                      {item.retrieved_chunk_ids.map((cid: string, idx: number) => (
                                        <Fragment key={idx}>
                                          <ChunkIdBadge chunkId={cid} cache={chunkContentCache} onFetch={fetchChunkContent} />
                                          {idx < item.retrieved_chunk_ids.length - 1 && <span>,</span>}
                                        </Fragment>
                                      ))}
                                    </div>
                                  </div>
                                  {evalReport.mode === "full" && item.answer && (
                                    <div>
                                      <p className="text-xs text-gray-500 mb-1">
                                        LLM 回答：
                                      </p>
                                      <p className="text-xs bg-white p-2 rounded border">
                                        {item.answer}
                                      </p>
                                    </div>
                                  )}
                                  {evalReport.mode === "full" &&
                                    item.retrieved_chunks && (
                                      <div>
                                        <p className="text-xs text-gray-500 mb-1">
                                          检索到的 Chunk 内容：
                                        </p>
                                        {item.retrieved_chunks.map(
                                          (chunk: string, j: number) => (
                                            <p
                                              key={j}
                                              className="text-xs bg-white p-2 rounded border mb-1"
                                            >
                                              {chunk}
                                            </p>
                                          )
                                        )}
                                      </div>
                                    )}
                                </div>
                              </td>
                            </tr>
                          )}
                        </Fragment>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            )}

            {/* 无报告时的提示 */}
            {evalTab === "report" && !evalReport && (
              <div className="bg-white rounded-lg shadow p-6 text-center text-gray-400">
                请先执行评估
              </div>
            )}
          </div>
        )}

        {/* 工具管理 */}
        {activeTab === "tools" && (
          <div className="space-y-6">
            <div className="bg-white rounded-lg shadow p-6">
              <div className="flex justify-between items-center mb-4">
                <h2 className="text-lg font-semibold">工具管理</h2>
                <button
                  onClick={() => { setShowToolForm(true); setEditingTool(null); setToolForm({ name: "", description: "", endpoint: "", method: "POST", auth_type: "none" }); }}
                  className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700"
                >
                  新增工具
                </button>
              </div>
              <p className="text-sm text-gray-500 mb-4">
                配置 Agent 可调用的工具，支持动态加载和租户级隔离
              </p>

              {tools.length === 0 ? (
                <p className="text-gray-400 text-sm text-center py-8">暂无工具，点击"新增工具"添加</p>
              ) : (
                <table className="w-full text-sm">
                  <thead>
                    <tr className="text-left text-gray-500 border-b">
                      <th className="py-2">工具名称</th>
                      <th>描述</th>
                      <th>端点</th>
                      <th>方法</th>
                      <th>状态</th>
                      <th>操作</th>
                    </tr>
                  </thead>
                  <tbody>
                    {tools.map((tool) => (
                      <tr key={tool.id} className="border-b hover:bg-gray-50">
                        <td className="py-3 font-medium">{tool.name}</td>
                        <td className="text-gray-600 max-w-xs truncate">{tool.description}</td>
                        <td className="text-gray-500 text-xs font-mono">{tool.endpoint}</td>
                        <td><span className="px-2 py-0.5 bg-gray-100 rounded text-xs">{tool.method}</span></td>
                        <td>
                          <button
                            onClick={() => handleToggleTool(tool)}
                            className={`px-2 py-0.5 rounded text-xs cursor-pointer ${
                              tool.is_active ? "bg-green-100 text-green-700" : "bg-red-100 text-red-700"
                            }`}
                          >
                            {tool.is_active ? "启用" : "禁用"}
                          </button>
                        </td>
                        <td>
                          <div className="flex gap-2">
                            <button onClick={() => handleEditTool(tool)} className="text-blue-600 hover:underline text-xs">编辑</button>
                            <button onClick={() => handleDeleteTool(tool.id)} className="text-red-600 hover:underline text-xs">删除</button>
                          </div>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              )}
            </div>

            {/* 工具表单弹窗 */}
            {showToolForm && (
              <div className="bg-white rounded-lg shadow p-6">
                <h3 className="text-md font-semibold mb-4">{editingTool ? "编辑工具" : "新增工具"}</h3>
                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <label className="text-sm text-gray-600">工具名称</label>
                    <input
                      type="text"
                      value={toolForm.name}
                      onChange={(e) => setToolForm((prev) => ({ ...prev, name: e.target.value }))}
                      placeholder="如：query_order"
                      className="w-full px-3 py-2 border rounded-lg mt-1"
                    />
                  </div>
                  <div>
                    <label className="text-sm text-gray-600">请求方法</label>
                    <select
                      value={toolForm.method}
                      onChange={(e) => setToolForm((prev) => ({ ...prev, method: e.target.value }))}
                      className="w-full px-3 py-2 border rounded-lg mt-1"
                    >
                      <option value="POST">POST</option>
                      <option value="GET">GET</option>
                    </select>
                  </div>
                  <div className="col-span-2">
                    <label className="text-sm text-gray-600">工具描述（给 LLM 看的）</label>
                    <input
                      type="text"
                      value={toolForm.description}
                      onChange={(e) => setToolForm((prev) => ({ ...prev, description: e.target.value }))}
                      placeholder="如：查询订单状态，返回订单详情"
                      className="w-full px-3 py-2 border rounded-lg mt-1"
                    />
                  </div>
                  <div className="col-span-2">
                    <label className="text-sm text-gray-600">调用端点</label>
                    <input
                      type="text"
                      value={toolForm.endpoint}
                      onChange={(e) => setToolForm((prev) => ({ ...prev, endpoint: e.target.value }))}
                      placeholder="如：https://api.example.com/query"
                      className="w-full px-3 py-2 border rounded-lg mt-1"
                    />
                  </div>
                  <div>
                    <label className="text-sm text-gray-600">认证方式</label>
                    <select
                      value={toolForm.auth_type}
                      onChange={(e) => setToolForm((prev) => ({ ...prev, auth_type: e.target.value }))}
                      className="w-full px-3 py-2 border rounded-lg mt-1"
                    >
                      <option value="none">无认证</option>
                      <option value="bearer">Bearer Token</option>
                      <option value="api_key">API Key</option>
                    </select>
                  </div>
                </div>
                <div className="flex gap-2 mt-6">
                  <button
                    onClick={handleSaveTool}
                    disabled={!toolForm.name || !toolForm.description || !toolForm.endpoint}
                    className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50"
                  >
                    {editingTool ? "保存修改" : "创建工具"}
                  </button>
                  <button
                    onClick={() => { setShowToolForm(false); setEditingTool(null); }}
                    className="px-4 py-2 bg-gray-200 text-gray-700 rounded-lg hover:bg-gray-300"
                  >
                    取消
                  </button>
                </div>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}

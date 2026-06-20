"use client";
import { useState } from "react";
import Link from "next/link";
import axios from "axios";

const t = typeof window !== "undefined" ? localStorage.getItem("token") : "";
const h = { Authorization: `Bearer ${t}` };

export default function TeacherAssignments() {
  const [mode, setMode] = useState<"list" | "create">("list");
  const [assignments, setAssignments] = useState<any[]>([]);
  const [title, setTitle] = useState("");
  const [desc, setDesc] = useState("");
  const [questions, setQuestions] = useState<string[]>([""]);
  const [loading, setLoading] = useState(false);
  const [loaded, setLoaded] = useState(false);

  const loadAssignments = async () => {
    setLoading(true);
    const r = await axios.get("/api/assignments/teacher", { headers: h });
    setAssignments(r.data);
    setLoading(false);
    setLoaded(true);
  };
  if (!loaded && !loading) loadAssignments();

  const addQuestion = () => setQuestions([...questions, ""]);
  const updateQ = (i: number, v: string) => {
    const q = [...questions]; q[i] = v; setQuestions(q);
  };
  const createAssignment = async () => {
    setLoading(true);
    await axios.post("/api/assignments/teacher", {
      title,
      description: desc,
      questions: questions.filter(q => q.trim()).map((q, i) => ({
        id: i + 1, question: q, answer: ""
      }))
    }, { headers: h });
    setTitle(""); setDesc(""); setQuestions([""]);
    setMode("list");
    loadAssignments();
    setLoading(false);
  };

  return (
    <div className="min-h-screen bg-gray-50">
      <nav className="bg-white border-b px-6 py-4"><div className="max-w-4xl mx-auto flex items-center justify-between">
        <Link href="/teacher/dashboard" className="text-[#6366f1] hover:underline text-sm">← 返回</Link>
        <span className="font-semibold">作业管理</span>
        <button onClick={() => setMode(mode === "list" ? "create" : "list")} className="text-sm text-[#6366f1]">
          {mode === "list" ? "+ 发布新作业" : "← 返回列表"}
        </button>
      </div></nav>
      <main className="max-w-4xl mx-auto px-6 py-8">
        {mode === "list" ? (
          <div className="space-y-4">
            <h2 className="text-xl font-bold">已发布的作业</h2>
            {assignments.map((a: any) => (
              <div key={a.id} className="card">
                <div className="font-medium text-lg">{a.title}</div>
                <div className="text-sm text-gray-500 mt-1">{a.description}</div>
                <div className="text-xs text-gray-400 mt-2">{a.questions_count}道题 · {a.submissions}人已提交</div>
              </div>
            ))}
            {assignments.length === 0 && <div className="text-center py-12 text-gray-400">暂无作业</div>}
          </div>
        ) : (
          <div className="card">
            <h2 className="text-xl font-bold mb-4">发布新作业</h2>
            <div className="space-y-4">
              <div><label className="block text-sm font-medium mb-1">作业标题</label>
                <input className="input" value={title} onChange={e => setTitle(e.target.value)} placeholder="单元测试一" /></div>
              <div><label className="block text-sm font-medium mb-1">描述</label>
                <textarea className="input" value={desc} onChange={e => setDesc(e.target.value)} placeholder="请在周五前完成" /></div>
              <div><label className="block text-sm font-medium mb-1">题目</label>
                {questions.map((q, i) => (
                  <div key={i} className="flex gap-2 mb-2">
                    <span className="mt-2 text-sm font-medium">{i+1}.</span>
                    <input className="input flex-1" value={q} onChange={e => updateQ(i, e.target.value)} placeholder={`第${i+1}题`} />
                  </div>
                ))}
                <button onClick={addQuestion} className="text-sm text-[#6366f1] mt-1">+ 添加题目</button>
              </div>
              <button onClick={createAssignment} disabled={loading || !title.trim()} className="btn-primary w-full">
                {loading ? "发布中..." : "📢 发布作业"}
              </button>
            </div>
          </div>
        )}
      </main>
    </div>
  );
}
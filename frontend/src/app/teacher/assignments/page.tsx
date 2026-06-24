"use client";
import { useState, useEffect } from "react";
import Link from "next/link";
import axios from "axios";

export default function TeacherAssignments() {
  const [mode, setMode] = useState<"list" | "create">("list");
  const [assignments, setAssignments] = useState<any[]>([]);
  const [title, setTitle] = useState("");
  const [desc, setDesc] = useState("");
  const [questions, setQuestions] = useState<string[]>([""]);
  const [classId, setClassId] = useState<number | 0>(0);
  const [classList, setClassList] = useState<any[]>([]);
  const [loading, setLoading] = useState(false);
  const [loaded, setLoaded] = useState(false);

  const headers = () => ({ Authorization: `Bearer ${typeof window !== "undefined" ? localStorage.getItem("token") : ""}` });

  useEffect(() => {
    if (!loaded && !loading) {
      loadAssignments();
      loadClasses();
    }
  }, []);

  const loadAssignments = async () => {
    setLoading(true);
    try {
      const r = await axios.get("/api/assignments/teacher", { headers: headers() });
      setAssignments(r.data);
    } catch (e) {} finally {
      setLoading(false);
      setLoaded(true);
    }
  };
  const loadClasses = async () => {
    try {
      const r = await axios.get("/api/classes", { headers: headers() });
      setClassList(r.data);
    } catch {}
  };

  const addQuestion = () => setQuestions([...questions, ""]);
  const updateQ = (i: number, v: string) => {
    const q = [...questions]; q[i] = v; setQuestions(q);
  };
  const createAssignment = async () => {
    setLoading(true);
    await axios.post("/api/assignments/teacher", {
      title,
      description: desc,
      class_id: classId || null,
      questions: questions.filter(q => q.trim()).map((q, i) => ({
        id: i + 1, question: q, answer: ""
      }))
    }, { headers: headers() });
    setTitle(""); setDesc(""); setQuestions([""]); setClassId(0);
    setMode("list");
    loadAssignments();
    setLoading(false);
  };

  return (
    <div className="min-h-screen bg-gray-50">
      <div className="navbar">
        <div className="max-w-4xl mx-auto h-14 flex items-center justify-between px-6">
          <Link href="/teacher/dashboard" className="text-sm text-indigo-600 font-medium">← 返回</Link>
          <span className="font-semibold">📋 作业管理</span>
          <button onClick={() => { setMode(mode === "list" ? "create" : "list"); loadClasses(); }}
            className="btn-secondary btn-sm">
            {mode === "list" ? "+ 发布新作业" : "← 返回列表"}
          </button>
        </div>
      </div>
      <main className="max-w-4xl mx-auto px-6 py-8">
        {mode === "list" ? (
          <>
            <h2 className="text-xl font-bold mb-6">📋 已发布的作业</h2>
            <div className="space-y-3">
              {assignments.map((a: any) => (
                <div key={a.id} className="card">
                  <div className="flex items-center justify-between">
                    <div className="font-semibold text-lg">{a.title}</div>
                    <span className="badge badge-gray">{a.class_name || "📢 广播"}</span>
                  </div>
                  <div className="text-sm text-gray-500 mt-1">{a.description}</div>
                  <div className="text-xs text-gray-400 mt-2">{a.questions_count} 道题 · {a.submissions} 人已提交</div>
                </div>
              ))}
              {assignments.length === 0 && <div className="empty-state"><div className="icon">📋</div><div className="text">暂无作业</div></div>}
            </div>
          </>
        ) : (
          <div className="card max-w-2xl mx-auto">
            <h2 className="text-xl font-bold mb-6">📝 发布新作业</h2>
            <div className="space-y-4">
              <div>
                <label className="block text-sm font-medium mb-1.5">作业标题</label>
                <input className="input" value={title} onChange={e => setTitle(e.target.value)} placeholder="单元测试一" />
              </div>
              <div>
                <label className="block text-sm font-medium mb-1.5">描述</label>
                <textarea className="input min-h-[80px]" value={desc} onChange={e => setDesc(e.target.value)} placeholder="请在周五前完成" />
              </div>
              <div>
                <label className="block text-sm font-medium mb-1.5">发布到班级</label>
                <select className="input" value={classId} onChange={e => setClassId(Number(e.target.value))}>
                  <option value={0}>📢 广播（所有学生可见）</option>
                  {classList.map((c: any) => (
                    <option key={c.id} value={c.id}>🏫 {c.name}</option>
                  ))}
                </select>
              </div>
              <div>
                <label className="block text-sm font-medium mb-1.5">题目</label>
                {questions.map((q, i) => (
                  <div key={i} className="flex gap-2 mb-2">
                    <span className="mt-2.5 text-sm font-medium w-6">{i+1}.</span>
                    <input className="input flex-1" value={q} onChange={e => updateQ(i, e.target.value)} placeholder={`第${i+1}题`} />
                  </div>
                ))}
                <button onClick={addQuestion} className="text-sm text-indigo-600 mt-1 font-medium">+ 添加题目</button>
              </div>
              <button onClick={createAssignment} disabled={loading || !title.trim()}
                className="btn-primary w-full mt-4">
                {loading ? "发布中..." : "📢 发布作业"}
              </button>
            </div>
          </div>
        )}
      </main>
    </div>
  );
}

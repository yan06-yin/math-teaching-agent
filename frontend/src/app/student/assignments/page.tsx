"use client";
import { useState } from "react";
import Link from "next/link";
import axios from "axios";

const token = () => typeof window !== "undefined" ? localStorage.getItem("token") : "";
const hdrs = () => ({ Authorization: `Bearer ${token()}` });

export default function StudentAssignments() {
  const [assignments, setAssignments] = useState<any[]>([]);
  const [loading, setLoading] = useState(false);
  const [loaded, setLoaded] = useState(false);
  const [selected, setSelected] = useState<any>(null);
  const [answers, setAnswers] = useState<string[]>([]);

  const load = async () => {
    setLoading(true);
    const r = await axios.get("/api/assignments/student", { headers: hdrs() });
    setAssignments(r.data);
    setLoaded(true);
    setLoading(false);
  };
  if (!loaded && !loading) load();

  const openAssignment = (a: any) => {
    setSelected(a);
    setAnswers(new Array((a.questions || []).length).fill(""));
  };

  const submit = async () => {
    setLoading(true);
    try {
      await axios.post(`/api/assignments/student/${selected.id}/submit`, {
        answers: answers.map((a, i) => ({ question_index: i, answer: a }))
      }, { headers: hdrs() });
      alert("提交成功！");
      setSelected(null);
      load();
    } catch (e: any) { alert("提交失败：" + (e.response?.data?.detail || e.message)); }
    finally { setLoading(false); }
  };

  return (
    <div className="min-h-screen bg-gray-50">
      <nav className="bg-white border-b px-6 py-4"><div className="max-w-4xl mx-auto flex items-center justify-between">
        <Link href="/student/dashboard" className="text-[#6366f1] hover:underline text-sm">← 返回</Link>
        <span className="font-semibold">教师布置的作业</span><div />
      </div></nav>
      <main className="max-w-4xl mx-auto px-6 py-8">
        {!selected ? (
          <div className="space-y-4">
            <h2 className="text-xl font-bold">待完成作业</h2>
            {assignments.filter((a: any) => !a.submitted).map((a: any) => (
              <div key={a.id} className="card cursor-pointer hover:shadow-md" onClick={() => openAssignment(a)}>
                <div className="font-medium text-lg">{a.title}</div>
                <div className="text-sm text-gray-500">{a.description}</div>
                <div className="text-xs text-gray-400 mt-2">{a.questions?.length || 0}道题</div>
              </div>
            ))}
            {assignments.filter((a: any) => !a.submitted).length === 0 && (
              <div className="text-center py-12 text-gray-400">暂无待完成的作业</div>
            )}
            <h2 className="text-xl font-bold mt-8">已完成作业</h2>
            {assignments.filter((a: any) => a.submitted).map((a: any) => (
              <div key={a.id} className="card">
                <div className="font-medium">{a.title}</div>
                <div className="text-xs text-green-600 mt-1">
                  得分：{a.submission?.score ?? "待批改"} · {new Date(a.submission?.submitted_at).toLocaleDateString("zh-CN")}
                </div>
              </div>
            ))}
          </div>
        ) : (
          <div className="space-y-6">
            <button onClick={() => setSelected(null)} className="text-[#6366f1] text-sm">← 返回</button>
            <div className="card"><h2 className="text-xl font-bold mb-2">{selected.title}</h2><p className="text-gray-500">{selected.description}</p></div>
            {selected.questions?.map((q: any, i: number) => (
              <div key={i} className="card">
                <div className="flex items-start gap-3">
                  <span className="w-8 h-8 bg-indigo-100 text-indigo-600 rounded-full flex items-center justify-center text-sm font-medium flex-shrink-0">{i+1}</span>
                  <div className="flex-1">
                    <p className="text-gray-900 mb-2">{q.question}</p>
                    <textarea className="input min-h-[80px]" placeholder="输入你的答案..." value={answers[i] || ""} onChange={e => { const a=[...answers]; a[i]=e.target.value; setAnswers(a); }} />
                  </div>
                </div>
              </div>
            ))}
            <button onClick={submit} disabled={loading} className="btn-primary w-full py-3">{loading ? "提交中..." : "✅ 提交作业"}</button>
          </div>
        )}
      </main>
    </div>
  );
}
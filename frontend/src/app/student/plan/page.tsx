"use client";
import { useState, useEffect } from "react";
import Link from "next/link";
import axios from "axios";

export default function PlanPage() {
  const [plan, setPlan] = useState<any[] | null>(null);
  const [loading, setLoading] = useState(true);
  const [generating, setGenerating] = useState(false);
  const [subject, setSubject] = useState("math");
  const [error, setError] = useState("");

  const token = typeof window !== "undefined" ? localStorage.getItem("token") : "";
  const headers = { Authorization: `Bearer ${token}` };
  const sid = typeof window !== "undefined" ? localStorage.getItem("studentId") : "";

  useEffect(() => {
    if (!token) { window.location.href = "/"; return; }
    loadLatestPlan();
  }, []);

  const loadLatestPlan = async () => {
    try {
      const r = await axios.get("/api/exam/my", { headers });
      if (r.data.length > 0) {
        const d = await axios.get(`/api/exam/${r.data[0].id}/report`, { headers });
        setPlan(d.data.learning_plan || null);
      }
    } catch {} finally { setLoading(false); }
  };

  const handleGenerate = async () => {
    if (!sid) return;
    setGenerating(true);
    setError("");
    try {
      const r = await axios.post(`/api/analysis/student/${sid}/generate-learning-plan?subject=${subject}&days=14`, {}, { headers });
      setPlan(r.data.plan || []);
    } catch (e: any) {
      setError(e.response?.data?.detail || e.message || "生成失败");
    } finally { setGenerating(false); }
  };

  if (loading) return <div className="min-h-screen flex items-center justify-center"><div className="spinner"></div></div>;

  return (
    <div className="min-h-screen bg-gray-50">
      <nav className="bg-white border-b px-6 py-4"><div className="max-w-4xl mx-auto flex items-center justify-between"><Link href="/student/dashboard" className="text-[#6366f1] hover:underline text-sm">← 返回首页</Link><span className="font-semibold">学习计划</span><div /></div></nav>
      <main className="max-w-4xl mx-auto px-6 py-8">
        {/* 学科选择和生成按钮 */}
        <div className="card mb-6">
          <div className="flex items-center gap-4 flex-wrap">
            <span className="text-sm font-medium text-gray-600">学科：</span>
            <div className="flex gap-2">
              {[
                { key: "math", label: "数学", icon: "📐" },
                { key: "chinese", label: "语文", icon: "📝" },
                { key: "english", label: "英语", icon: "🔤" },
              ].map(s => (
                <button key={s.key} onClick={() => setSubject(s.key)}
                  className={`text-sm px-3 py-1.5 rounded-full transition-all ${subject === s.key ? "bg-indigo-100 text-indigo-700 font-semibold" : "bg-gray-100 text-gray-500 hover:bg-gray-200"}`}>
                  {s.icon} {s.label}
                </button>
              ))}
            </div>
            <button onClick={handleGenerate} disabled={generating}
              className="btn-primary btn-sm ml-auto">
              {generating ? "⏳ 生成中..." : "🤖 生成学习计划"}
            </button>
          </div>
          {error && <p className="text-red-500 text-sm mt-2">⚠️ {error}</p>}
        </div>

        {!plan || plan.length === 0 ? (
          <div className="card text-center py-16">
            <div className="text-5xl mb-4">📋</div>
            <h3 className="text-lg font-semibold text-gray-700 mb-2">暂无学习计划</h3>
            <p className="text-gray-500 mb-2">点击上方按钮，AI 会根据你的学习数据自动生成计划</p>
          </div>
        ) : (
          <div className="card">
            <h3 className="font-semibold text-lg mb-6">为你定制的学习计划</h3>
            <div className="space-y-4">
              {plan.map((item: any, i: number) => (
                <div key={i} className="flex items-start gap-4 p-4 bg-gradient-to-r from-[#eef2ff] to-purple-50 rounded-xl">
                  <span className="flex-shrink-0 w-10 h-10 bg-[#6366f1] text-white rounded-full flex items-center justify-center font-bold">{i+1}</span>
                  <div>
                    <div className="font-medium">{item.day || item.topic}</div>
                    <div className="text-sm text-gray-500">{item.topic} · {item.focus}</div>
                    <div className="flex gap-4 mt-2 text-xs text-gray-400">
                      {item.duration_minutes && <span>⏱ {item.duration_minutes}分</span>}
                      {item.exercises && <span>📝 {item.exercises}题</span>}
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}
      </main>
    </div>
  );
}

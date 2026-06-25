"use client";
import { useState, useEffect } from "react";
import Link from "next/link";
import axios from "axios";

export default function PlanPage() {
  const [plan, setPlan] = useState<any[] | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const t = localStorage.getItem("token");
    if (!t) { window.location.href = "/"; return; }
    axios.get("/api/exam/my", { headers: { Authorization: `Bearer ${t}` } }).then(async r => {
      if (r.data.length > 0) {
        const d = await axios.get(`/api/exam/${r.data[0].id}/report`, { headers: { Authorization: `Bearer ${t}` } });
        setPlan(d.data.learning_plan || null);
      }
    }).catch(() => {}).finally(() => setLoading(false));
  }, []);

  if (loading) return <div className="min-h-screen flex items-center justify-center"><div className="spinner"></div></div>;

  return (
    <div className="min-h-screen bg-gray-50">
      <nav className="bg-white border-b px-6 py-4"><div className="max-w-4xl mx-auto flex items-center justify-between"><Link href="/student/dashboard" className="text-[#6366f1] hover:underline text-sm">← 返回首页</Link><span className="font-semibold">学习计划</span><div /></div></nav>
      <main className="max-w-4xl mx-auto px-6 py-8">
        {!plan || plan.length === 0 ? (
          <div className="card text-center py-16"><div className="text-5xl mb-4">📋</div><h3 className="text-lg font-semibold text-gray-700 mb-2">暂无学习计划</h3><p className="text-gray-500 mb-6">先参加一次智能考试</p><Link href="/student/exam" className="btn-primary inline-block">去参加考试</Link></div>
        ) : (
          <div className="card"><h3 className="font-semibold text-lg mb-6">为你定制的学习计划</h3>
            <div className="space-y-4">{plan.map((item, i) => (
              <div key={i} className="flex items-start gap-4 p-4 bg-gradient-to-r from-[#eef2ff] to-purple-50 rounded-xl">
                <span className="flex-shrink-0 w-10 h-10 bg-[#6366f1] text-white rounded-full flex items-center justify-center font-bold">{i+1}</span>
                <div><div className="font-medium">{item.day || item.topic}</div><div className="text-sm text-gray-500">{item.topic} · {item.focus}</div><div className="flex gap-4 mt-2 text-xs text-gray-400">{item.duration_minutes && <span>⏱ {item.duration_minutes}分</span>}{item.exercises && <span>📝 {item.exercises}题</span>}</div></div>
              </div>
            ))}</div>
          </div>
        )}
      </main>
    </div>
  );
}

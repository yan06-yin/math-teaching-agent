"use client";
import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import axios from "axios";
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from "recharts";

export default function StudentDashboard() {
  const router = useRouter();
  const [profile, setProfile] = useState<any>(null);
  const [trends, setTrends] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const token = localStorage.getItem("token");
    if (!token) { router.push("/"); return; }
    const sid = localStorage.getItem("studentId");
    if (!sid) return;
    (async () => {
      try {
        const [pr, tr] = await Promise.all([
          axios.get(`/api/analysis/student/${sid}`, { headers: { Authorization: `Bearer ${token}` } }),
          axios.get(`/api/analysis/class/${sid}/trends`, { headers: { Authorization: `Bearer ${token}` } }),
        ]);
        setProfile(pr.data);
        setTrends(tr.data);
      } catch {} finally { setLoading(false); }
    })();
  }, [router]);

  if (loading) return <div className="min-h-screen flex items-center justify-center"><div className="spinner"></div></div>;

  const td = trends.map(t => ({ name: new Date(t.date).toLocaleDateString("zh-CN", { month: "short", day: "numeric" }), score: t.score }));
  const un = typeof window !== "undefined" ? localStorage.getItem("userName") || "同学" : "同学";

  return (
    <div className="min-h-screen bg-gray-50">
      <nav className="bg-white border-b border-gray-100 px-6 py-4">
        <div className="max-w-7xl mx-auto flex items-center justify-between">
          <div className="flex items-center gap-3"><span className="text-xl">📐</span><span className="font-bold text-lg">数学教学智能体</span></div>
          <Link href="/" className="text-sm text-[#6366f1] hover:underline">退出</Link>
        </div>
      </nav>
      <main className="max-w-7xl mx-auto px-6 py-8">
        <div className="mb-8"><h2 className="text-2xl font-bold text-gray-900">你好，{un} 👋</h2><p className="text-gray-500 mt-1">今天也要加油学习哦！</p></div>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-8">
          <Link href="/student/upload" className="card hover:shadow-md block"><div className="text-3xl mb-2">📸</div><div className="font-medium">拍照批改</div><div className="text-sm text-gray-500">上传作业自动批改</div></Link>
          <Link href="/student/exam" className="card hover:shadow-md block"><div className="text-3xl mb-2">📝</div><div className="font-medium">智能考试</div><div className="text-sm text-gray-500">针对性出题组卷</div></Link>
          <Link href="/student/report" className="card hover:shadow-md block"><div className="text-3xl mb-2">📊</div><div className="font-medium">诊断报告</div><div className="text-sm text-gray-500">学习情况分析</div></Link>
          <Link href="/student/plan" className="card hover:shadow-md block"><div className="text-3xl mb-2">🗓️</div><div className="font-medium">学习计划</div><div className="text-sm text-gray-500">个性化学习方案</div></Link>
        </div>
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          <div className="card">
            <h3 className="font-semibold text-gray-900 mb-4">成绩趋势</h3>
            {td.length > 0 ? (
              <ResponsiveContainer width="100%" height={280}>
                <LineChart data={td}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
                  <XAxis dataKey="name" tick={{ fontSize: 12 }} />
                  <YAxis domain={[0, 100]} tick={{ fontSize: 12 }} />
                  <Tooltip />
                  <Line type="monotone" dataKey="score" stroke="#6366f1" strokeWidth={2} dot={{ fill: "#6366f1" }} />
                </LineChart>
              </ResponsiveContainer>
            ) : <div className="text-center py-12 text-gray-400">暂无成绩数据</div>}
          </div>
          <div className="card">
            <h3 className="font-semibold text-gray-900 mb-4">学习概览</h3>
            {profile ? (
              <div className="space-y-4">
                <div className="grid grid-cols-3 gap-4">
                  <div className="text-center p-3 bg-[#eef2ff] rounded-lg"><div className="text-2xl font-bold text-[#6366f1]">{profile.total_homework}</div><div className="text-xs text-gray-500 mt-1">作业次数</div></div>
                  <div className="text-center p-3 bg-[#ecfdf5] rounded-lg"><div className="text-2xl font-bold text-[#10b981]">{profile.total_exams}</div><div className="text-xs text-gray-500 mt-1">考试次数</div></div>
                  <div className="text-center p-3 bg-[#fffbeb] rounded-lg"><div className="text-2xl font-bold text-[#f59e0b]">{profile.avg_score}</div><div className="text-xs text-gray-500 mt-1">平均分</div></div>
                </div>
                {profile.weaknesses?.length > 0 && (
                  <div><div className="text-sm font-medium text-gray-700 mb-2">薄弱知识点</div><div className="flex flex-wrap gap-2">{profile.weaknesses.map((wp: string) => (<span key={wp} className="px-3 py-1 bg-red-50 text-red-600 text-sm rounded-full">{wp}</span>))}</div></div>
                )}
              </div>
            ) : <div className="text-center py-8 text-gray-400">暂无数据</div>}
          </div>
        </div>
      </main>
    </div>
  );
}

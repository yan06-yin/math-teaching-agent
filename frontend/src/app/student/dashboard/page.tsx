"use client";
import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import axios from "axios";
import { useToast } from "@/app/toast";
import { TableSkeleton, CardSkeleton } from "@/app/skeleton";
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from "recharts";

export default function StudentDashboard() {
  const { toast } = useToast();
  const router = useRouter();
  const [profile, setProfile] = useState<any>(null);
  const [trends, setTrends] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [myClass, setMyClass] = useState<any>(null);
  const [inviteCode, setInviteCode] = useState("");
  const [joinLoading, setJoinLoading] = useState(false);

  const headers = () => ({ Authorization: `Bearer ${localStorage.getItem("token")}` });

  useEffect(() => {
    const token = localStorage.getItem("token");
    if (!token) { router.push("/"); return; }
    const sid = localStorage.getItem("studentId");
    if (!sid) return;
    (async () => {
      try {
        const [pr, tr, cls] = await Promise.all([
          axios.get(`/api/analysis/student/${sid}`, { headers: headers() }),
          axios.get(`/api/analysis/class/${sid}/trends`, { headers: headers() }),
          axios.get(`/api/classes/my`, { headers: headers() }).catch(() => null),
        ]);
        setProfile(pr.data); setTrends(tr.data);
        if (cls?.data) setMyClass(cls.data);
      } catch {} finally { setLoading(false); }
    })();
  }, [router]);

  const handleJoin = async () => {
    if (!inviteCode.trim()) return;
    setJoinLoading(true);
    try {
      const r = await axios.post("/api/classes/join", { code: inviteCode.trim() }, { headers: headers() });
      setMyClass({ class_id: r.data.class_id, class_name: r.data.class_name });
      setInviteCode("");
    } catch (e: any) { toast("加入失败：", "error"); }
    finally { setJoinLoading(false); }
  };

  if (loading) return <div className="min-h-screen flex items-center justify-center"><div className="spinner spinner-lg"></div></div>;

  const td = trends.map(t => ({ name: new Date(t.date).toLocaleDateString("zh-CN", { month: "short", day: "numeric" }), score: t.score }));
  const un = typeof window !== "undefined" ? localStorage.getItem("userName") || "同学" : "同学";

  return (
    <div className="min-h-screen bg-gray-50">
      {/* Nav */}
      <div className="navbar">
        <div className="max-w-7xl mx-auto px-6 h-14 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <span className="text-xl">📐</span>
            <span className="font-bold text-lg">数学教学智能体</span>
          </div>
          <button onClick={() => { localStorage.clear(); window.location.href = "/"; }}
            className="btn-secondary btn-sm">退出</button>
        </div>
      </div>

      <main className="max-w-7xl mx-auto px-6 py-8">
        {/* Greeting */}
        <div className="mb-8">
          <h2 className="text-2xl font-bold text-gray-900">你好，{un} 👋</h2>
          <p className="text-gray-500 mt-1 text-sm">今天也要加油学习哦！</p>
        </div>

        {/* 班级信息 */}
        {myClass ? (
          <div className="card mb-6 bg-gradient-to-r from-indigo-50 to-white border-indigo-100">
            <div className="flex items-center gap-3">
              <span className="text-2xl">🏫</span>
              <div>
                <span className="font-semibold text-lg">{myClass.class_name}</span>
                <span className="text-xs text-gray-400 ml-2">{myClass.school_level}</span>
                <div className="text-xs text-gray-400">教师：{myClass.teacher_name}</div>
              </div>
            </div>
          </div>
        ) : (
          <div className="card mb-6 bg-gradient-to-r from-amber-50 to-white border-amber-100">
            <div className="flex flex-col sm:flex-row items-start sm:items-center gap-3">
              <span className="text-2xl">🏫</span>
              <span className="font-medium text-sm">加入班级</span>
              <input className="input !w-48" placeholder="输入邀请码" value={inviteCode} onChange={e => setInviteCode(e.target.value)} />
              <button onClick={handleJoin} disabled={joinLoading || !inviteCode.trim()}
                className="btn-primary btn-sm">{joinLoading ? "加入中..." : "立即加入"}</button>
            </div>
          </div>
        )}

        {/* Feature cards */}
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-8">
          {[
            { href: "/student/assignments", icon: "📋", title: "教师作业", desc: "查看和提交作业" },
            { href: "/student/upload", icon: "📸", title: "拍照批改", desc: "上传作业自动批改" },
            { href: "/student/exam", icon: "📝", title: "智能考试", desc: "针对性出题组卷" },
            { href: "/student/report", icon: "📊", title: "诊断报告", desc: "学习情况分析" },
            { href: "/student/plan", icon: "🗓️", title: "学习计划", desc: "个性化学习方案" },
          ].map((item, i) => (
            <Link key={i} href={item.href}
              className="card card-hover !p-4 !rounded-xl group">
              <div className="text-2xl mb-2 group-hover:scale-110 transition-transform">{item.icon}</div>
              <div className="font-semibold text-sm">{item.title}</div>
              <div className="text-xs text-gray-400 mt-0.5">{item.desc}</div>
            </Link>
          ))}
        </div>

        {/* Charts */}
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          <div className="card">
            <h3 className="font-semibold mb-4">📈 成绩趋势</h3>
            {td.length > 0 ? (
              <ResponsiveContainer width="100%" height={280}>
                <LineChart data={td}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" />
                  <XAxis dataKey="name" tick={{ fontSize: 12 }} />
                  <YAxis domain={[0, 100]} tick={{ fontSize: 12 }} />
                  <Tooltip />
                  <Line type="monotone" dataKey="score" stroke="#6366f1" strokeWidth={2.5} dot={{ fill: "#6366f1", strokeWidth: 2 }} />
                </LineChart>
              </ResponsiveContainer>
            ) : <div className="empty-state"><div className="icon">📈</div><div className="text">暂无成绩数据</div></div>}
          </div>

          <div className="card">
            <h3 className="font-semibold mb-4">📊 学习概览</h3>
            {profile ? (
              <div className="space-y-4">
                <div className="grid grid-cols-3 gap-3">
                  <div className="text-center p-3 bg-indigo-50 rounded-xl"><div className="text-2xl font-bold text-indigo-600">{profile.total_homework}</div><div className="text-xs text-gray-500 mt-1">作业次数</div></div>
                  <div className="text-center p-3 bg-green-50 rounded-xl"><div className="text-2xl font-bold text-green-600">{profile.total_exams}</div><div className="text-xs text-gray-500 mt-1">考试次数</div></div>
                  <div className="text-center p-3 bg-amber-50 rounded-xl"><div className="text-2xl font-bold text-amber-500">{profile.avg_score}</div><div className="text-xs text-gray-500 mt-1">平均分</div></div>
                </div>
                {profile.weaknesses?.length > 0 && (
                  <div>
                    <div className="text-sm font-medium text-gray-700 mb-2">📌 薄弱知识点</div>
                    <div className="flex flex-wrap gap-1.5">
                      {profile.weaknesses.map((wp: string) => (
                        <span key={wp} className="px-2.5 py-1 bg-red-50 text-red-600 text-xs rounded-full border border-red-100">{wp}</span>
                      ))}
                    </div>
                  </div>
                )}
                {profile.strengths?.length > 0 && (
                  <div>
                    <div className="text-sm font-medium text-gray-700 mb-2">⭐ 优势知识点</div>
                    <div className="flex flex-wrap gap-1.5">
                      {profile.strengths.map((sp: string) => (
                        <span key={sp} className="px-2.5 py-1 bg-green-50 text-green-600 text-xs rounded-full border border-green-100">{sp}</span>
                      ))}
                    </div>
                  </div>
                )}
              </div>
            ) : <div className="empty-state"><div className="icon">📊</div><div className="text">暂无数据</div></div>}
          </div>
        </div>
      </main>
    </div>
  );
}

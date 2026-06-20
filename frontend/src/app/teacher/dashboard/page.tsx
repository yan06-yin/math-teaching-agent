"use client";
import { useState, useEffect } from "react";
import Link from "next/link";
import axios from "axios";
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Cell } from "recharts";

type Tab = "overview" | "errors" | "students" | "student" | "kp";

export default function TeacherDashboard() {
  const [tab, setTab] = useState<Tab>("overview");
  const [data, setData] = useState<any>(null);
  const [errors, setErrors] = useState<any[]>([]);
  const [studentList, setStudentList] = useState<any[]>([]);
  const [selStudent, setSelStudent] = useState<any>(null);
  const [stErrors, setStErrors] = useState<any[]>([]);
  const [kpData, setKpData] = useState<any>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const t = localStorage.getItem("token");
    if (!t || localStorage.getItem("userType") !== "teacher") return;

    const headers = { Authorization: `Bearer ${t}` };

    // 分别请求，互不影响
    axios.get("/api/teacher/dashboard", { headers })
      .then(r => setData(r.data))
      .catch(() => {});

    axios.get("/api/teacher/errors", { headers })
      .then(r => setErrors(r.data))
      .catch(() => {});

    axios.get("/api/teacher/students", { headers })
      .then(r => setStudentList(r.data))
      .catch(() => {});

    setLoading(false);
  }, []);

  const viewStudent = async (id: number) => {
    const r = await axios.get(`/api/teacher/student/${id}/errors`, { headers: { Authorization: `Bearer ${localStorage.getItem("token")}` } });
    setSelStudent(r.data.student); setStErrors(r.data.errors); setTab("student");
  };
  const viewKP = async (kp: string) => {
    const r = await axios.get(`/api/teacher/errors/knowledge-point/${encodeURIComponent(kp)}`, { headers: { Authorization: `Bearer ${localStorage.getItem("token")}` } });
    setKpData(r.data); setTab("kp");
  };

  if (loading) return <div className="min-h-screen flex items-center justify-center"><div className="spinner"></div></div>;

  return (
    <div className="min-h-screen bg-gray-50">
      <nav className="bg-white border-b px-6 py-4"><div className="max-w-7xl mx-auto flex items-center justify-between">
        <span className="text-xl">👨‍🏫</span><span className="font-bold text-lg">教师端</span>
        <div className="flex gap-4 items-center">
          <Link href="/teacher/assignments" className="text-sm text-[#6366f1] hover:underline">发布作业</Link>
          <Link href="/" className="text-sm text-[#6366f1] hover:underline">退出</Link>
        </div>
      </div></nav>
      <div className="bg-white border-b"><div className="max-w-7xl mx-auto px-6 flex gap-1">
        {(["overview","errors","students"] as Tab[]).map(t => (
          <button key={t} onClick={() => setTab(t)} className={`px-4 py-3 text-sm font-medium border-b-2 transition cursor-pointer ${tab === t ? "border-[#6366f1] text-[#6366f1]" : "border-transparent text-gray-500"}`}>
            {t === "overview" && "📊 总览"}{t === "errors" && "❌ 错题汇总"}{t === "students" && "👥 学生列表"}
          </button>
        ))}
        {tab === "student" && <span className="px-4 py-3 text-sm font-medium border-b-2 border-[#6366f1] text-[#6366f1]">👤 {selStudent?.name||""}</span>}
        {tab === "kp" && <span className="px-4 py-3 text-sm font-medium border-b-2 border-[#6366f1] text-[#6366f1]">📖 {kpData?.knowledge_point||""}</span>}
      </div></div>
      <main className="max-w-7xl mx-auto px-6 py-8">
        {/* 总览 */}
        {tab === "overview" && (
          <>
            <div className="grid grid-cols-4 gap-4 mb-8">
              <div className="card"><div className="text-3xl font-bold text-[#6366f1]">{data?.total_students||0}</div><div className="text-sm text-gray-500">学生总数</div></div>
              <div className="card"><div className="text-3xl font-bold text-green-600">{data?.total_homework||0}</div><div className="text-sm text-gray-500">作业提交</div></div>
              <div className="card"><div className="text-3xl font-bold text-indigo-600">{data?.total_exams||0}</div><div className="text-sm text-gray-500">考试次数</div></div>
              <div className="card"><div className="text-3xl font-bold text-amber-600">{data?.class_avg_score||0}</div><div className="text-sm text-gray-500">班级均分</div></div>
            </div>
            <div className="card mb-8">
              <h3 className="font-semibold mb-4">需关注学生排行</h3>
              {data?.top_error_students?.length > 0 ? (
                <table className="w-full text-sm">{data?.top_error_students?.map((s: any, i: number) => (
                  <tr key={s.student_id} className="border-b hover:bg-gray-50 cursor-pointer" onClick={() => viewStudent(s.student_id)}>
                    <td className="py-3 px-2">{i+1}</td><td className="py-3 px-2 font-medium">{s.name}</td><td className="py-3 px-2 text-right">{s.weak_points}知识点</td><td className="py-3 px-2 text-right text-red-600">{s.total_errors}错题</td>
                  </tr>
                ))}</table>
              ) : <div className="text-center py-8 text-gray-400">暂无错题数据</div>}
            </div>
          </>
        )}

        {/* 错题汇总 */}
        {tab === "errors" && (
          <>
            <div className="card mb-6"><h3 className="font-semibold mb-4">全班知识点错误率</h3>
              <ResponsiveContainer width="100%" height={300}><BarChart data={errors.slice(0,10)}><CartesianGrid strokeDasharray="3 3"/><XAxis dataKey="knowledge_point" tick={{fontSize:12}} interval={0} angle={-30} textAnchor="end" height={80}/><YAxis/><Tooltip/><Bar dataKey="error_rate" fill="#ef4444" radius={[4,4,0,0]}/></BarChart></ResponsiveContainer>
            </div>
            <div className="card"><h3 className="font-semibold mb-4">知识点明细</h3>
              {errors.map((e, i) => (
                <div key={i} className="border rounded-lg p-4 mb-3 hover:bg-gray-50 cursor-pointer" onClick={() => viewKP(e.knowledge_point)}>
                  <div className="flex justify-between"><span className="font-medium">{e.knowledge_point}</span><span className="text-sm text-gray-500">{e.error_count}次</span></div>
                  <div className="text-xs text-gray-400 mt-1">{e.affected_students}人 · 错误率{e.error_rate}%</div>
                </div>
              ))}
              {errors.length === 0 && <div className="text-center py-8 text-gray-400">暂无错题记录</div>}
            </div>
          </>
        )}

        {/* 学生列表 */}
        {tab === "students" && (
          <div className="card">
            <h3 className="font-semibold mb-4">👥 全部学生（共{studentList.length}人）</h3>
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead><tr className="border-b text-gray-500">
                  <th className="text-left py-3 px-2">姓名</th><th className="text-left py-3 px-2">学号</th><th className="text-left py-3 px-2">学段</th>
                  <th className="text-center py-3 px-2">作业</th><th className="text-center py-3 px-2">考试</th><th className="text-center py-3 px-2">均分</th>
                  <th className="text-center py-3 px-2">错题</th><th className="text-center py-3 px-2">最近活动</th><th className="text-center py-3 px-2">操作</th>
                </tr></thead>
                <tbody>
                  {studentList.map((s: any) => (
                    <tr key={s.id} className="border-b hover:bg-gray-50">
                      <td className="py-3 px-2 font-medium">{s.name}</td>
                      <td className="py-3 px-2">{s.student_id}</td>
                      <td className="py-3 px-2">{s.level}</td>
                      <td className="py-3 px-2 text-center">{s.homework_count}</td>
                      <td className="py-3 px-2 text-center">{s.exam_count}</td>
                      <td className="py-3 px-2 text-center font-medium">{s.avg_score}</td>
                      <td className="py-3 px-2 text-center text-red-600">{s.error_count}</td>
                      <td className="py-3 px-2 text-center text-xs text-gray-400">{s.last_login ? new Date(s.last_login).toLocaleDateString("zh-CN") : "未登录"}</td>
                      <td className="py-3 px-2 text-center">
                        <button onClick={() => viewStudent(s.id)} className="text-xs text-[#6366f1] hover:underline">错题详情</button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        )}

        {/* 学生错题详情 */}
        {tab === "student" && (
          <div>
            <button onClick={() => setTab("students")} className="text-[#6366f1] text-sm mb-4">← 返回学生列表</button>
            {selStudent && <div className="card mb-4"><h3 className="font-semibold text-lg">{selStudent.name} 的错题</h3><span className="text-sm text-gray-500">{selStudent.level}</span></div>}
            {stErrors.length > 0 ? stErrors.map((e, i) => (
              <div key={i} className="card p-4 mb-3"><div className="font-medium text-red-800">{e.knowledge_point}</div><div className="text-sm mt-1">{e.question}</div><div className="text-xs text-gray-500 mt-1">答：{e.student_answer} → 正确：{e.correct_answer}</div></div>
            )) : <div className="text-center py-8 text-gray-400">暂无错题</div>}
          </div>
        )}

        {/* 知识点钻取 */}
        {tab === "kp" && kpData && (
          <div>
            <button onClick={() => setTab("errors")} className="text-[#6366f1] text-sm mb-4">← 返回</button>
            {kpData.errors?.map((e: any, i: number) => (
              <div key={i} className="card p-4 mb-3"><span className="font-medium text-indigo-600">{e.student_name}</span><div className="text-sm mt-1">{e.question}</div><div className="text-xs text-gray-500 mt-1">答：{e.student_answer} → {e.correct_answer}</div></div>
            ))}
            {(!kpData.errors || kpData.errors.length === 0) && <div className="text-center py-8 text-gray-400">暂无错题</div>}
          </div>
        )}
      </main>
    </div>
  );
}
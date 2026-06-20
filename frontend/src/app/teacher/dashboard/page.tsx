"use client";
import { useState, useEffect } from "react";
import Link from "next/link";
import axios from "axios";
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Cell } from "recharts";

type Tab = "overview" | "errors" | "student" | "kp";

export default function TeacherDashboard() {
  const [tab, setTab] = useState<Tab>("overview");
  const [data, setData] = useState<any>(null);
  const [errors, setErrors] = useState<any[]>([]);
  const [selStudent, setSelStudent] = useState<any>(null);
  const [stErrors, setStErrors] = useState<any[]>([]);
  const [kpData, setKpData] = useState<any>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const t = localStorage.getItem("token");
    if (!t || localStorage.getItem("userType") !== "teacher") return;
    Promise.all([
      axios.get("/api/teacher/dashboard", { headers: { Authorization: `Bearer ${t}` } }),
      axios.get("/api/teacher/errors", { headers: { Authorization: `Bearer ${t}` } }),
    ]).then(([d, e]) => { setData(d.data); setErrors(e.data); }).catch(() => {}).finally(() => setLoading(false));
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
      <nav className="bg-white border-b px-6 py-4"><div className="max-w-7xl mx-auto flex items-center justify-between"><span className="text-xl">👨‍🏫</span><span className="font-bold text-lg">教师端</span><Link href="/" className="text-sm text-[#6366f1] hover:underline">退出</Link></div></nav>
      <div className="bg-white border-b"><div className="max-w-7xl mx-auto px-6 flex gap-1">
        {(["overview","errors","student","kp"] as Tab[]).map(t => (
          <button key={t} onClick={() => setTab(t)} className={`px-4 py-3 text-sm font-medium border-b-2 transition cursor-pointer ${tab === t ? "border-[#6366f1] text-[#6366f1]" : "border-transparent text-gray-500"}`}>
            {t === "overview" && "总览"}{t === "errors" && "知识点错误汇总"}{t === "student" && `学生: ${selStudent?.name||""}`}{t === "kp" && `知识点: ${kpData?.knowledge_point||""}`}
          </button>
        ))}
      </div></div>
      <main className="max-w-7xl mx-auto px-6 py-8">
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
              <table className="w-full text-sm">{data?.top_error_students?.map((s: any, i: number) => (
                <tr key={s.student_id} className="border-b hover:bg-gray-50 cursor-pointer" onClick={() => viewStudent(s.student_id)}>
                  <td className="py-3 px-2">{i+1}</td><td className="py-3 px-2 font-medium">{s.name}</td><td className="py-3 px-2 text-right">{s.weak_points}知识点</td><td className="py-3 px-2 text-right text-red-600">{s.total_errors}错题</td>
                </tr>
              ))}</table>
            </div>
          </>
        )}
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
            </div>
          </>
        )}
        {tab === "student" && (
          <div className="space-y-3">{stErrors.map((e, i) => (
            <div key={i} className="card p-4"><div className="font-medium text-red-800">{e.knowledge_point}</div><div className="text-sm mt-1">{e.question}</div><div className="text-xs text-gray-500 mt-1">答案：{e.student_answer} → 正确：{e.correct_answer}</div></div>
          ))}</div>
        )}
        {tab === "kp" && kpData && (
          <div className="space-y-3">{kpData.errors?.map((e: any, i: number) => (
            <div key={i} className="card p-4"><span className="font-medium text-indigo-600">{e.student_name}</span><div className="text-sm mt-1">{e.question}</div><div className="text-xs text-gray-500 mt-1">答：{e.student_answer} → {e.correct_answer}</div></div>
          ))}</div>
        )}
      </main>
    </div>
  );
}

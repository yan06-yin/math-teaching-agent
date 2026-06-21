"use client";
import { useState, useEffect } from "react";
import axios from "axios";
import Link from "next/link";

type Tab = "overview" | "teachers" | "classes" | "students" | "assignments" | "exams";

export default function AdminDashboard() {
  const [tab, setTab] = useState<Tab>("overview");
  const [data, setData] = useState<any>(null);
  const [teachers, setTeachers] = useState<any[]>([]);
  const [classes, setClasses] = useState<any[]>([]);
  const [students, setStudents] = useState<any[]>([]);
  const [assignments, setAssignments] = useState<any[]>([]);
  const [exams, setExams] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);

  const headers = () => ({ Authorization: `Bearer ${localStorage.getItem("token")}` });

  const loadAll = async () => {
    setLoading(true);
    const [d, t, c, s, a, e] = await Promise.all([
      axios.get("/api/admin/dashboard", { headers: headers() }).catch(() => null),
      axios.get("/api/admin/teachers", { headers: headers() }).catch(() => null),
      axios.get("/api/admin/classes", { headers: headers() }).catch(() => null),
      axios.get("/api/admin/students", { headers: headers() }).catch(() => null),
      axios.get("/api/admin/assignments", { headers: headers() }).catch(() => null),
      axios.get("/api/admin/exams", { headers: headers() }).catch(() => null),
    ]);
    if (d?.data) setData(d.data);
    if (t?.data) setTeachers(t.data);
    if (c?.data) setClasses(c.data);
    if (s?.data) setStudents(s.data.students || s.data);
    if (a?.data) setAssignments(a.data);
    if (e?.data) setExams(e.data);
    setLoading(false);
  };

  useEffect(() => { loadAll(); }, []);

  const handleDeleteTeacher = async (id: number, name: string) => {
    if (!confirm(`确定删除教师「${name}」？会级联删除所有班级和学生关联。`)) return;
    try {
      await axios.delete(`/api/admin/teachers/${id}`, { headers: headers() });
      setTeachers(prev => prev.filter(t => t.id !== id));
    } catch (e: any) { alert("删除失败：" + (e.response?.data?.detail || e.message)); }
  };

  const handleDeleteClass = async (id: number) => {
    if (!confirm("确定删除该班级？")) return;
    try {
      await axios.delete(`/api/admin/classes/${id}`, { headers: headers() });
      loadAll();
    } catch (e: any) { alert("删除失败：" + (e.response?.data?.detail || e.message)); }
  };

  const handleAssignStudent = async (studentId: number) => {
    const classId = prompt("请输入目标班级 ID：");
    if (!classId) return;
    try {
      await axios.post("/api/admin/students/assign", { student_id: studentId, class_id: parseInt(classId) }, { headers: headers() });
      loadAll();
    } catch (e: any) { alert("分配失败：" + (e.response?.data?.detail || e.message)); }
  };

  const handleRemoveClass = async (studentId: number, name: string) => {
    if (!confirm(`将「${name}」移出班级？`)) return;
    try {
      await axios.delete(`/api/admin/students/${studentId}/class`, { headers: headers() });
      setStudents(prev => prev.map(s => s.id === studentId ? { ...s, class_name: null } : s));
    } catch (e: any) { alert("操作失败：" + (e.response?.data?.detail || e.message)); }
  };

  if (loading) return <div className="min-h-screen flex items-center justify-center"><div className="spinner spinner-lg"></div></div>;

  const SIDEBAR: { key: Tab; label: string }[] = [
    { key: "overview", label: "📊 总览" },
    { key: "teachers", label: "👨‍🏫 教师管理" },
    { key: "classes", label: "🏫 班级管理" },
    { key: "students", label: "👥 学生管理" },
    { key: "assignments", label: "📋 作业管理" },
    { key: "exams", label: "📝 考试/成绩" },
  ];

  return (
    <div className="min-h-screen bg-gray-50 flex">
      {/* Sidebar */}
      <div className="sidebar hidden md:flex">
        <div className="sidebar-header">⚙️ 系统管理</div>
        {SIDEBAR.map(item => (
          <button key={item.key} onClick={() => setTab(item.key)}
            className={`sidebar-item ${tab === item.key ? "active" : ""}`}>{item.label}</button>
        ))}
        <div className="sidebar-footer">
          <button onClick={() => { localStorage.clear(); window.location.href = "/"; }}
            className="sidebar-item text-red-500 hover:bg-red-50">🚪 退出管理</button>
        </div>
      </div>

      {/* Mobile tabs */}
      <div className="md:hidden fixed top-0 left-0 right-0 bg-white border-b z-50 flex overflow-x-auto px-2 py-2 gap-1">
        {SIDEBAR.map(item => (
          <button key={item.key} onClick={() => setTab(item.key)}
            className={`px-3 py-1.5 rounded-lg text-xs whitespace-nowrap ${tab === item.key ? "bg-indigo-100 text-indigo-700 font-medium" : "text-gray-500"}`}>{item.label}</button>
        ))}
      </div>

      <main className="flex-1 p-4 md:p-8 overflow-auto md:mt-0 mt-14">
        {/* 总览 */}
        {tab === "overview" && (
          <>
            <h2 className="text-xl font-bold mb-6">📊 系统总览</h2>
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">
              <div className="stat-card"><div className="value text-indigo-600">{data?.teacher_count||0}</div><div className="label">👨‍🏫 教师</div></div>
              <div className="stat-card"><div className="value text-green-600">{data?.class_count||0}</div><div className="label">🏫 班级</div></div>
              <div className="stat-card"><div className="value text-indigo-500">{data?.student_count||0}</div><div className="label">👥 学生</div></div>
              <div className="stat-card"><div className="value text-amber-500">{data?.avg_score||0}</div><div className="label">📊 平均分</div></div>
            </div>
            <div className="grid grid-cols-3 gap-4">
              <div className="stat-card"><div className="value text-green-600">{data?.assignment_count||0}</div><div className="label">📋 已发布作业</div></div>
              <div className="stat-card"><div className="value text-blue-600">{data?.homework_count||0}</div><div className="label">📄 作业提交</div></div>
              <div className="stat-card"><div className="value text-purple-600">{data?.exam_count||0}</div><div className="label">📝 考试次数</div></div>
            </div>
          </>
        )}

        {/* 教师管理 */}
        {tab === "teachers" && (
          <>
            <h2 className="text-xl font-bold mb-6">👨‍🏫 教师管理</h2>
            <div className="card !p-0">
              <div className="table-wrap !border-0">
                <table className="w-full">
                  <thead><tr><th>姓名</th><th>用户名</th><th>学校</th><th>班级数</th><th>学生数</th><th>注册时间</th><th>操作</th></tr></thead>
                  <tbody>{teachers.length > 0 ? teachers.map((t: any) => (
                    <tr key={t.id}>
                      <td className="font-medium">{t.name}</td>
                      <td className="text-gray-500">{t.username}</td>
                      <td>{t.school || <span className="text-gray-400">-</span>}</td>
                      <td className="text-center"><span className="badge badge-primary">{t.class_count}</span></td>
                      <td className="text-center"><span className="badge badge-gray">{t.student_count}</span></td>
                      <td className="text-center text-xs text-gray-400">{t.created_at ? new Date(t.created_at).toLocaleDateString("zh-CN") : "-"}</td>
                      <td className="text-center"><button onClick={() => handleDeleteTeacher(t.id, t.name)} className="btn-danger btn-sm">删除</button></td>
                    </tr>
                  )) : <tr><td colSpan={7} className="text-center py-8 text-gray-400">暂无教师</td></tr>}</tbody>
                </table>
              </div>
            </div>
          </>
        )}

        {/* 班级管理 */}
        {tab === "classes" && (
          <>
            <h2 className="text-xl font-bold mb-6">🏫 班级管理</h2>
            <div className="card !p-0">
              <div className="table-wrap !border-0">
                <table className="w-full">
                  <thead><tr><th>班级名称</th><th>所属教师</th><th>学段</th><th>学生数</th><th>创建时间</th><th>操作</th></tr></thead>
                  <tbody>{classes.length > 0 ? classes.map((c: any) => (
                    <tr key={c.id}>
                      <td className="font-medium">{c.name}</td>
                      <td>{c.teacher_name}</td>
                      <td><span className="badge badge-gray">{c.school_level}</span></td>
                      <td className="text-center"><span className="badge badge-primary">{c.student_count}</span></td>
                      <td className="text-center text-xs text-gray-400">{c.created_at ? new Date(c.created_at).toLocaleDateString("zh-CN") : "-"}</td>
                      <td className="text-center"><button onClick={() => handleDeleteClass(c.id)} className="btn-danger btn-sm">删除</button></td>
                    </tr>
                  )) : <tr><td colSpan={6} className="text-center py-8 text-gray-400">暂无班级</td></tr>}</tbody>
                </table>
              </div>
            </div>
          </>
        )}

        {/* 学生管理 */}
        {tab === "students" && (
          <>
            <h2 className="text-xl font-bold mb-6">👥 学生管理</h2>
            <div className="card !p-0">
              <div className="table-wrap !border-0 overflow-x-auto">
                <table className="w-full">
                  <thead><tr><th>姓名</th><th>学号</th><th>学段</th><th>班级</th><th>作业</th><th>考试</th><th>均分</th><th>操作</th></tr></thead>
                  <tbody>{students.length > 0 ? students.map((s: any) => (
                    <tr key={s.id}>
                      <td className="font-medium">{s.name}</td>
                      <td className="text-gray-500">{s.student_id}</td>
                      <td><span className="badge badge-gray">{s.school_level}</span></td>
                      <td>{s.class_name || <span className="text-gray-400 text-xs">未分配</span>}</td>
                      <td className="text-center">{s.homework_count}</td>
                      <td className="text-center">{s.exam_count}</td>
                      <td className="text-center font-semibold">{s.avg_score}</td>
                      <td className="text-center whitespace-nowrap">
                        {s.class_name ? (
                          <button onClick={() => handleRemoveClass(s.id, s.name)} className="btn-danger btn-sm mr-1">移出</button>
                        ) : (
                          <button onClick={() => handleAssignStudent(s.id)} className="btn-primary btn-sm">分配</button>
                        )}
                      </td>
                    </tr>
                  )) : <tr><td colSpan={8} className="text-center py-8 text-gray-400">暂无学生</td></tr>}</tbody>
                </table>
              </div>
            </div>
          </>
        )}

        {/* 作业管理 */}
        {tab === "assignments" && (
          <>
            <h2 className="text-xl font-bold mb-6">📋 作业管理</h2>
            <div className="card !p-0">
              <div className="table-wrap !border-0">
                <table className="w-full">
                  <thead><tr><th>标题</th><th>教师</th><th>班级</th><th>题目数</th><th>提交数</th><th>发布时间</th></tr></thead>
                  <tbody>{assignments.length > 0 ? assignments.map((a: any) => (
                    <tr key={a.id}>
                      <td className="font-medium">{a.title}</td>
                      <td>{a.teacher_name}</td>
                      <td><span className="badge badge-gray">{a.class_name || "广播"}</span></td>
                      <td className="text-center">{a.questions_count}</td>
                      <td className="text-center"><span className="badge badge-primary">{a.submissions}</span></td>
                      <td className="text-center text-xs text-gray-400">{a.created_at ? new Date(a.created_at).toLocaleDateString("zh-CN") : "-"}</td>
                    </tr>
                  )) : <tr><td colSpan={6} className="text-center py-8 text-gray-400">暂无作业</td></tr>}</tbody>
                </table>
              </div>
            </div>
          </>
        )}

        {/* 考试/成绩 */}
        {tab === "exams" && (
          <>
            <h2 className="text-xl font-bold mb-6">📝 考试/成绩</h2>
            <div className="card !p-0">
              <div className="table-wrap !border-0">
                <table className="w-full">
                  <thead><tr><th>学生</th><th>学号</th><th>分数</th><th>题数</th><th>考试时间</th></tr></thead>
                  <tbody>{exams.length > 0 ? exams.map((e: any) => (
                    <tr key={e.id}>
                      <td className="font-medium">{e.student_name}</td>
                      <td className="text-gray-500">{e.student_id}</td>
                      <td className="text-center"><span className="font-semibold text-indigo-600">{e.score}</span></td>
                      <td className="text-center">{e.questions_count}</td>
                      <td className="text-center text-xs text-gray-400">{e.created_at ? new Date(e.created_at).toLocaleString("zh-CN") : "-"}</td>
                    </tr>
                  )) : <tr><td colSpan={5} className="text-center py-8 text-gray-400">暂无考试记录</td></tr>}</tbody>
                </table>
              </div>
            </div>
          </>
        )}
      </main>
    </div>
  );
}

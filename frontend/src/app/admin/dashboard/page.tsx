"use client";
import { useState, useEffect } from "react";
import axios from "axios";

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

  useEffect(() => {
    const t = localStorage.getItem("token");
    if (!t) { window.location.href = "/"; return; }
    setLoading(true);
    Promise.all([
      axios.get("/api/admin/dashboard", { headers: headers() }).catch(() => null),
      axios.get("/api/admin/teachers", { headers: headers() }).catch(() => null),
      axios.get("/api/admin/classes", { headers: headers() }).catch(() => null),
      axios.get("/api/admin/students", { headers: headers() }).catch(() => null),
      axios.get("/api/admin/assignments", { headers: headers() }).catch(() => null),
      axios.get("/api/admin/exams", { headers: headers() }).catch(() => null),
    ]).then(([d, t, c, s, a, e]) => {
      if (d?.data) setData(d.data);
      if (t?.data) setTeachers(t.data);
      if (c?.data) setClasses(c.data);
      if (s?.data) setStudents(s.data);
      if (a?.data) setAssignments(a.data);
      if (e?.data) setExams(e.data);
    }).finally(() => setLoading(false));
  }, []);

  const handleDeleteTeacher = async (id: number, name: string) => {
    if (!confirm(`确定删除教师「${name}」？会删除其所有班级、学生关联和作业。`)) return;
    try {
      await axios.delete(`/api/admin/teachers/${id}`, { headers: headers() });
      setTeachers(prev => prev.filter(t => t.id !== id));
      alert("删除成功");
    } catch (e: any) { alert("删除失败：" + (e.response?.data?.detail || e.message)); }
  };

  const handleDeleteClass = async (id: number) => {
    if (!confirm(`确定删除该班级？`)) return;
    try {
      await axios.delete(`/api/admin/classes/${id}`, { headers: headers() });
      setClasses(prev => prev.filter(c => c.id !== id));
      alert("删除成功");
    } catch (e: any) { alert("删除失败：" + (e.response?.data?.detail || e.message)); }
  };

  const handleAssignStudent = async (studentId: number) => {
    const classId = prompt("请输入目标班级 ID（可查看班级列表获取）:");
    if (!classId) return;
    try {
      await axios.post(`/api/admin/students/assign`, { student_id: studentId, class_id: parseInt(classId) }, { headers: headers() });
      // 刷新学生列表
      const r = await axios.get("/api/admin/students", { headers: headers() });
      setStudents(r.data);
      alert("分配成功");
    } catch (e: any) { alert("分配失败：" + (e.response?.data?.detail || e.message)); }
  };

  const handleRemoveClass = async (studentId: number, name: string) => {
    if (!confirm(`确定将「${name}」移出班级？`)) return;
    try {
      await axios.delete(`/api/admin/students/${studentId}/class`, { headers: headers() });
      setStudents(prev => prev.map(s => s.id === studentId ? { ...s, class_name: null } : s));
      alert("已移出班级");
    } catch (e: any) { alert("操作失败：" + (e.response?.data?.detail || e.message)); }
  };

  if (loading) return <div className="min-h-screen flex items-center justify-center"><div className="spinner"></div></div>;

  const Sidebar = () => (
    <div className="w-56 bg-white border-r min-h-screen p-4 flex flex-col gap-1">
      <div className="text-xl mb-6 px-3 font-bold">⚙️ 系统管理</div>
      {([
        { key: "overview", label: "📊 总览" },
        { key: "teachers", label: "👨‍🏫 教师管理" },
        { key: "classes", label: "🏫 班级管理" },
        { key: "students", label: "👥 学生管理" },
        { key: "assignments", label: "📋 作业管理" },
        { key: "exams", label: "📝 考试/成绩" },
      ] as { key: Tab; label: string }[]).map(item => (
        <button key={item.key} onClick={() => setTab(item.key)}
          className={`text-left px-3 py-2 rounded-lg text-sm transition cursor-pointer ${tab === item.key ? "bg-[#eef2ff] text-[#6366f1] font-medium" : "text-gray-600 hover:bg-gray-50"}`}>
          {item.label}
        </button>
      ))}
      <div className="mt-auto pt-4 border-t">
        <button onClick={() => { localStorage.clear(); window.location.href = "/"; }}
          className="w-full text-left px-3 py-2 text-sm text-red-500 hover:bg-red-50 rounded-lg">
          退出管理
        </button>
      </div>
    </div>
  );

  return (
    <div className="min-h-screen bg-gray-50 flex">
      <Sidebar />
      <main className="flex-1 p-6 overflow-auto">
        {/* 总览 */}
        {tab === "overview" && (
          <>
            <h2 className="text-xl font-bold mb-6">系统总览</h2>
            <div className="grid grid-cols-4 gap-4 mb-8">
              <div className="card"><div className="text-3xl font-bold text-[#6366f1]">{data?.teacher_count||0}</div><div className="text-sm text-gray-500">教师</div></div>
              <div className="card"><div className="text-3xl font-bold text-green-600">{data?.class_count||0}</div><div className="text-sm text-gray-500">班级</div></div>
              <div className="card"><div className="text-3xl font-bold text-indigo-600">{data?.student_count||0}</div><div className="text-sm text-gray-500">学生</div></div>
              <div className="card"><div className="text-3xl font-bold text-amber-600">{data?.avg_score||0}</div><div className="text-sm text-gray-500">平均分</div></div>
            </div>
            <div className="grid grid-cols-3 gap-4">
              <div className="card"><div className="text-xl font-bold text-green-600">{data?.assignment_count||0}</div><div className="text-sm text-gray-500">已发布作业</div></div>
              <div className="card"><div className="text-xl font-bold text-blue-600">{data?.homework_count||0}</div><div className="text-sm text-gray-500">作业提交</div></div>
              <div className="card"><div className="text-xl font-bold text-purple-600">{data?.exam_count||0}</div><div className="text-sm text-gray-500">考试次数</div></div>
            </div>
          </>
        )}

        {/* 教师管理 */}
        {tab === "teachers" && (
          <>
            <h2 className="text-xl font-bold mb-6">👨‍🏫 教师管理</h2>
            <div className="card overflow-x-auto">
              <table className="w-full text-sm">
                <thead><tr className="border-b text-gray-500">
                  <th className="text-left py-3 px-2">姓名</th><th className="text-left py-3 px-2">用户名</th>
                  <th className="text-left py-3 px-2">学校</th><th className="text-center py-3 px-2">班级数</th>
                  <th className="text-center py-3 px-2">学生数</th><th className="text-center py-3 px-2">注册时间</th>
                  <th className="text-center py-3 px-2">操作</th>
                </tr></thead>
                <tbody>
                  {teachers.map((t: any) => (
                    <tr key={t.id} className="border-b hover:bg-gray-50">
                      <td className="py-3 px-2 font-medium">{t.name}</td>
                      <td className="py-3 px-2">{t.username}</td>
                      <td className="py-3 px-2">{t.school}</td>
                      <td className="py-3 px-2 text-center">{t.class_count}</td>
                      <td className="py-3 px-2 text-center">{t.student_count}</td>
                      <td className="py-3 px-2 text-center text-xs text-gray-400">{t.created_at ? new Date(t.created_at).toLocaleDateString("zh-CN") : "-"}</td>
                      <td className="py-3 px-2 text-center">
                        <button onClick={() => handleDeleteTeacher(t.id, t.name)} className="text-xs text-red-600 hover:underline">删除</button>
                      </td>
                    </tr>
                  ))}
                  {teachers.length === 0 && <tr><td colSpan={7} className="text-center py-8 text-gray-400">暂无教师</td></tr>}
                </tbody>
              </table>
            </div>
          </>
        )}

        {/* 班级管理 */}
        {tab === "classes" && (
          <>
            <h2 className="text-xl font-bold mb-6">🏫 班级管理</h2>
            <div className="card overflow-x-auto">
              <table className="w-full text-sm">
                <thead><tr className="border-b text-gray-500">
                  <th className="text-left py-3 px-2">班级名称</th><th className="text-left py-3 px-2">所属教师</th>
                  <th className="text-left py-3 px-2">学段</th><th className="text-center py-3 px-2">学生数</th>
                  <th className="text-center py-3 px-2">创建时间</th><th className="text-center py-3 px-2">操作</th>
                </tr></thead>
                <tbody>
                  {classes.map((c: any) => (
                    <tr key={c.id} className="border-b hover:bg-gray-50">
                      <td className="py-3 px-2 font-medium">{c.name}</td>
                      <td className="py-3 px-2">{c.teacher_name}</td>
                      <td className="py-3 px-2">{c.school_level}</td>
                      <td className="py-3 px-2 text-center">{c.student_count}</td>
                      <td className="py-3 px-2 text-center text-xs text-gray-400">{c.created_at ? new Date(c.created_at).toLocaleDateString("zh-CN") : "-"}</td>
                      <td className="py-3 px-2 text-center">
                        <button onClick={() => handleDeleteClass(c.id)} className="text-xs text-red-600 hover:underline">删除</button>
                      </td>
                    </tr>
                  ))}
                  {classes.length === 0 && <tr><td colSpan={6} className="text-center py-8 text-gray-400">暂无班级</td></tr>}
                </tbody>
              </table>
            </div>
          </>
        )}

        {/* 学生管理 */}
        {tab === "students" && (
          <>
            <h2 className="text-xl font-bold mb-6">👥 学生管理</h2>
            <div className="card overflow-x-auto">
              <table className="w-full text-sm">
                <thead><tr className="border-b text-gray-500">
                  <th className="text-left py-3 px-2">姓名</th><th className="text-left py-3 px-2">学号</th>
                  <th className="text-left py-3 px-2">学段</th><th className="text-left py-3 px-2">所属班级</th>
                  <th className="text-center py-3 px-2">作业</th><th className="text-center py-3 px-2">考试</th>
                  <th className="text-center py-3 px-2">均分</th><th className="text-center py-3 px-2">操作</th>
                </tr></thead>
                <tbody>
                  {students.map((s: any) => (
                    <tr key={s.id} className="border-b hover:bg-gray-50">
                      <td className="py-3 px-2 font-medium">{s.name}</td>
                      <td className="py-3 px-2">{s.student_id}</td>
                      <td className="py-3 px-2">{s.school_level}</td>
                      <td className="py-3 px-2">{s.class_name || <span className="text-gray-400">未分配</span>}</td>
                      <td className="py-3 px-2 text-center">{s.homework_count}</td>
                      <td className="py-3 px-2 text-center">{s.exam_count}</td>
                      <td className="py-3 px-2 text-center font-medium">{s.avg_score}</td>
                      <td className="py-3 px-2 text-center">
                        {s.class_name ? (
                          <button onClick={() => handleRemoveClass(s.id, s.name)} className="text-xs text-orange-600 hover:underline mr-2">移出班级</button>
                        ) : (
                          <button onClick={() => handleAssignStudent(s.id)} className="text-xs text-[#6366f1] hover:underline">分配班级</button>
                        )}
                      </td>
                    </tr>
                  ))}
                  {students.length === 0 && <tr><td colSpan={8} className="text-center py-8 text-gray-400">暂无学生</td></tr>}
                </tbody>
              </table>
            </div>
          </>
        )}

        {/* 作业管理 */}
        {tab === "assignments" && (
          <>
            <h2 className="text-xl font-bold mb-6">📋 作业管理</h2>
            <div className="card overflow-x-auto">
              <table className="w-full text-sm">
                <thead><tr className="border-b text-gray-500">
                  <th className="text-left py-3 px-2">标题</th><th className="text-left py-3 px-2">教师</th>
                  <th className="text-left py-3 px-2">班级</th><th className="text-center py-3 px-2">题目数</th>
                  <th className="text-center py-3 px-2">提交数</th><th className="text-center py-3 px-2">发布时间</th>
                </tr></thead>
                <tbody>
                  {assignments.map((a: any) => (
                    <tr key={a.id} className="border-b hover:bg-gray-50">
                      <td className="py-3 px-2 font-medium">{a.title}</td>
                      <td className="py-3 px-2">{a.teacher_name}</td>
                      <td className="py-3 px-2">{a.class_name || "广播"}</td>
                      <td className="py-3 px-2 text-center">{a.questions_count}</td>
                      <td className="py-3 px-2 text-center">{a.submissions}</td>
                      <td className="py-3 px-2 text-center text-xs text-gray-400">{a.created_at ? new Date(a.created_at).toLocaleDateString("zh-CN") : "-"}</td>
                    </tr>
                  ))}
                  {assignments.length === 0 && <tr><td colSpan={6} className="text-center py-8 text-gray-400">暂无作业</td></tr>}
                </tbody>
              </table>
            </div>
          </>
        )}

        {/* 考试/成绩 */}
        {tab === "exams" && (
          <>
            <h2 className="text-xl font-bold mb-6">📝 考试/成绩</h2>
            <div className="card overflow-x-auto">
              <table className="w-full text-sm">
                <thead><tr className="border-b text-gray-500">
                  <th className="text-left py-3 px-2">学生</th><th className="text-left py-3 px-2">学号</th>
                  <th className="text-center py-3 px-2">分数</th><th className="text-center py-3 px-2">题数</th>
                  <th className="text-center py-3 px-2">考试时间</th>
                </tr></thead>
                <tbody>
                  {exams.map((e: any) => (
                    <tr key={e.id} className="border-b hover:bg-gray-50">
                      <td className="py-3 px-2 font-medium">{e.student_name}</td>
                      <td className="py-3 px-2">{e.student_id}</td>
                      <td className="py-3 px-2 text-center font-medium">{e.score}</td>
                      <td className="py-3 px-2 text-center">{e.questions_count}</td>
                      <td className="py-3 px-2 text-center text-xs text-gray-400">{e.created_at ? new Date(e.created_at).toLocaleString("zh-CN") : "-"}</td>
                    </tr>
                  ))}
                  {exams.length === 0 && <tr><td colSpan={5} className="text-center py-8 text-gray-400">暂无考试记录</td></tr>}
                </tbody>
              </table>
            </div>
          </>
        )}
      </main>
    </div>
  );
}

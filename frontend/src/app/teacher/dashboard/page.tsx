"use client";
import { useState, useEffect } from "react";
import Link from "next/link";
import axios from "axios";
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Cell } from "recharts";

type Tab = "overview" | "errors" | "students" | "student" | "kp" | "classes";

export default function TeacherDashboard() {
  const [tab, setTab] = useState<Tab>("overview");
  const [data, setData] = useState<any>(null);
  const [errors, setErrors] = useState<any[]>([]);
  const [studentList, setStudentList] = useState<any[]>([]);
  const [selStudent, setSelStudent] = useState<any>(null);
  const [stErrors, setStErrors] = useState<any[]>([]);
  const [kpData, setKpData] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [deletingId, setDeletingId] = useState<number | null>(null);
  const [deletingSelf, setDeletingSelf] = useState(false);

  // 班级管理状态
  const [classList, setClassList] = useState<any[]>([]);
  const [selClass, setSelClass] = useState<any>(null);
  const [showCreateClass, setShowCreateClass] = useState(false);
  const [newClassName, setNewClassName] = useState("");
  const [newClassLevel, setNewClassLevel] = useState("初中");
  const [addStudentId, setAddStudentId] = useState("");
  const [inviteCodes, setInviteCodes] = useState<any[]>([]);

  const headers = () => ({ Authorization: `Bearer ${localStorage.getItem("token")}` });

  const handleDeleteSelf = async () => {
    if (!confirm("确定要删除自己的教师账号吗？\n此操作不可恢复，所有数据将被永久删除。")) return;
    setDeletingSelf(true);
    try {
      await axios.delete("/api/auth/teacher/me", { headers: headers() });
      localStorage.removeItem("token");
      localStorage.removeItem("userType");
      localStorage.removeItem("userName");
      alert("账号已删除");
      window.location.href = "/";
    } catch (e: any) {
      alert("删除失败：" + (e.response?.data?.detail || e.message));
    } finally {
      setDeletingSelf(false);
    }
  };

  useEffect(() => {
    const t = localStorage.getItem("token");
    if (!t || localStorage.getItem("userType") !== "teacher") {
      setLoading(false);
      return;
    }

    const h = { Authorization: `Bearer ${t}` };
    let completed = 0;
    const allDone = () => { completed++; if (completed >= 3) setLoading(false); };

    axios.get("/api/teacher/dashboard", { headers: h })
      .then(r => setData(r.data))
      .catch(e => console.error('总览请求失败:', e))
      .finally(allDone);

    axios.get("/api/teacher/errors", { headers: h })
      .then(r => setErrors(r.data))
      .catch(e => console.error('错题请求失败:', e))
      .finally(allDone);

    axios.get("/api/teacher/students", { headers: h })
      .then(r => setStudentList(r.data))
      .catch(e => console.error('学生列表请求失败:', e))
      .finally(allDone);
  }, []);

  const viewStudent = async (id: number) => {
    const r = await axios.get(`/api/teacher/student/${id}/errors`, { headers: headers() });
    setSelStudent(r.data.student); setStErrors(r.data.errors); setTab("student");
  };
  const viewKP = async (kp: string) => {
    const r = await axios.get(`/api/teacher/errors/knowledge-point/${encodeURIComponent(kp)}`, { headers: headers() });
    setKpData(r.data); setTab("kp");
  };

  const handleDeleteStudent = async (id: number, name: string) => {
    if (!confirm(`确定要删除学生「${name}」吗？\n此操作不可恢复，相关作业、考试、错题记录也会被一并删除。`)) return;
    setDeletingId(id);
    try {
      await axios.delete(`/api/teacher/students/${id}`, { headers: headers() });
      setStudentList(prev => prev.filter(s => s.id !== id));
      alert("删除成功");
    } catch (e: any) {
      alert("删除失败：" + (e.response?.data?.detail || e.message));
    } finally {
      setDeletingId(null);
    }
  };

  // ===== 班级管理 =====
  const loadClasses = async () => {
    try {
      const r = await axios.get("/api/classes", { headers: headers() });
      setClassList(r.data);
    } catch {}
  };
  const loadClassDetail = async (id: number) => {
    try {
      const [cr, ir] = await Promise.all([
        axios.get(`/api/classes/${id}`, { headers: headers() }),
        axios.get(`/api/classes/${id}/invite-codes`, { headers: headers() }),
      ]);
      setSelClass(cr.data);
      setInviteCodes(ir.data);
    } catch {}
  };
  const handleCreateClass = async () => {
    if (!newClassName.trim()) return;
    try {
      await axios.post("/api/classes", { name: newClassName, school_level: newClassLevel }, { headers: headers() });
      setNewClassName(""); setShowCreateClass(false);
      loadClasses();
      alert("班级创建成功");
    } catch (e: any) { alert("创建失败：" + (e.response?.data?.detail || e.message)); }
  };
  const handleGenerateCode = async (classId: number) => {
    try {
      const r = await axios.post(`/api/classes/${classId}/invite-codes`, {}, { headers: headers() });
      setInviteCodes(prev => [r.data, ...prev]);
    } catch (e: any) { alert("生成失败：" + (e.response?.data?.detail || e.message)); }
  };
  const handleAddStudent = async (classId: number) => {
    if (!addStudentId.trim()) return;
    try {
      await axios.post(`/api/classes/${classId}/students`, { student_id: parseInt(addStudentId) }, { headers: headers() });
      setAddStudentId("");
      loadClassDetail(classId);
      alert("添加成功");
    } catch (e: any) { alert("添加失败：" + (e.response?.data?.detail || e.message)); }
  };
  const handleRemoveStudent = async (classId: number, studentId: number) => {
    if (!confirm("确定移出该学生？")) return;
    try {
      await axios.delete(`/api/classes/${classId}/students/${studentId}`, { headers: headers() });
      loadClassDetail(classId);
    } catch (e: any) { alert("操作失败：" + (e.response?.data?.detail || e.message)); }
  };
  const openClassTab = () => {
    setTab("classes");
    loadClasses();
  };

  if (loading) return <div className="min-h-screen flex items-center justify-center"><div className="spinner"></div></div>;

  return (
    <div className="min-h-screen bg-gray-50">
      <nav className="bg-white border-b px-6 py-4"><div className="max-w-7xl mx-auto flex items-center justify-between">
        <span className="text-xl">👨‍🏫</span><span className="font-bold text-lg">教师端</span>
        <div className="flex gap-4 items-center">
          <Link href="/teacher/assignments" className="text-sm text-[#6366f1] hover:underline">发布作业</Link>
          <button onClick={() => { localStorage.removeItem("token"); localStorage.removeItem("userType"); localStorage.removeItem("userName"); window.location.href = "/"; }} className="text-sm text-[#6366f1] hover:underline">退出</button>
          <button onClick={handleDeleteSelf} disabled={deletingSelf} className="text-sm text-red-500 hover:underline disabled:opacity-50">{deletingSelf ? "删除中..." : "注销账号"}</button>
        </div>
      </div></nav>
      <div className="bg-white border-b"><div className="max-w-7xl mx-auto px-6 flex gap-1">
        {(["overview","errors","students","classes"] as Tab[]).map(t => (
          <button key={t} onClick={t === "classes" ? openClassTab : () => setTab(t)} className={`px-4 py-3 text-sm font-medium border-b-2 transition cursor-pointer ${tab === t ? "border-[#6366f1] text-[#6366f1]" : "border-transparent text-gray-500"}`}>
            {t === "overview" && "📊 总览"}{t === "errors" && "❌ 错题汇总"}{t === "students" && "👥 学生列表"}{t === "classes" && "🏫 班级管理"}
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
                  <th className="text-center py-3 px-2">错题</th><th className="text-center py-3 px-2">最近活动</th><th className="text-center py-3 px-2">操作</th><th className="text-center py-3 px-2">删除</th>
                </tr></thead>
                <tbody>
                  {studentList.length === 0 ? (
                    <tr><td colSpan={10} className="text-center py-8 text-gray-400">暂无学生，请先创建班级并添加学生</td></tr>
                  ) : studentList.map((s: any) => (
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
                      <td className="py-3 px-2 text-center">
                        <button onClick={() => handleDeleteStudent(s.id, s.name)} disabled={deletingId === s.id}
                          className="text-xs text-red-600 hover:underline disabled:opacity-50">
                          {deletingId === s.id ? "删除中..." : "删除"}
                        </button>
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

        {/* 班级管理 */}
        {tab === "classes" && (
          <>
            <div className="flex items-center justify-between mb-6">
              <h2 className="text-xl font-bold">🏫 班级管理</h2>
              <button onClick={() => setShowCreateClass(true)} className="btn-primary text-sm">+ 创建班级</button>
            </div>

            {/* 创建班级弹窗 */}
            {showCreateClass && (
              <div className="card mb-6">
                <h3 className="font-semibold mb-4">创建新班级</h3>
                <div className="flex gap-4 items-end">
                  <div><label className="block text-xs font-medium mb-1">班级名称</label>
                    <input className="input" value={newClassName} onChange={e => setNewClassName(e.target.value)} placeholder="初二(3)班" /></div>
                  <div><label className="block text-xs font-medium mb-1">学段</label>
                    <select className="input" value={newClassLevel} onChange={e => setNewClassLevel(e.target.value)}>
                      <option value="小学">小学</option><option value="初中">初中</option><option value="高中">高中</option>
                    </select></div>
                  <button onClick={handleCreateClass} className="btn-primary text-sm">确认创建</button>
                  <button onClick={() => setShowCreateClass(false)} className="text-sm text-gray-500">取消</button>
                </div>
              </div>
            )}

            {/* 班级列表 */}
            {!selClass && (
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                {classList.map((c: any) => (
                  <div key={c.id} className="card hover:shadow-md cursor-pointer" onClick={() => loadClassDetail(c.id)}>
                    <div className="font-medium text-lg">{c.name}</div>
                    <div className="text-sm text-gray-500 mt-1">{c.school_level} · {c.student_count} 名学生</div>
                    <div className="text-xs text-gray-400 mt-2">{new Date(c.created_at).toLocaleDateString("zh-CN")} 创建</div>
                  </div>
                ))}
                {classList.length === 0 && <div className="text-center py-8 text-gray-400 col-span-2">还没有班级，点击上方创建</div>}
              </div>
            )}

            {/* 班级详情 */}
            {selClass && (
              <div>
                <button onClick={() => { setSelClass(null); loadClasses(); }} className="text-[#6366f1] text-sm mb-4">← 返回班级列表</button>
                <div className="card mb-6">
                  <div className="flex items-center justify-between">
                    <div><h3 className="font-semibold text-lg">{selClass.name}</h3>
                      <span className="text-xs text-gray-500">{selClass.school_level} · {selClass.student_count} 名学生</span>
                    </div>
                    <div className="flex gap-2">
                      <button onClick={() => handleGenerateCode(selClass.id)} className="btn-primary text-xs">生成邀请码</button>
                    </div>
                  </div>

                  {/* 邀请码列表 */}
                  {inviteCodes.length > 0 && (
                    <div className="mt-4">
                      <h4 className="text-sm font-medium mb-2">🔑 邀请码</h4>
                      <div className="flex flex-wrap gap-2">
                        {inviteCodes.map((c: any) => (
                          <div key={c.id} className={`px-3 py-1 rounded text-sm font-mono border ${c.is_active ? 'bg-green-50 border-green-200 text-green-800' : 'bg-gray-50 border-gray-200 text-gray-400'}`}>
                            <span>{c.code}</span>
                            <button className="ml-2 text-xs text-gray-400 hover:text-gray-600"
                              onClick={() => navigator.clipboard.writeText(c.code).then(() => alert("已复制"))}>
                              复制
                            </button>
                            <span className="ml-2 text-xs">{c.used_count}/{c.max_used_count || '∞'}</span>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}

                  {/* 手动添加学生 */}
                  <div className="mt-4 flex gap-2 items-end">
                    <div><label className="block text-xs font-medium mb-1">添加学生（输入学号）</label>
                      <input className="input" placeholder="学生ID" value={addStudentId} onChange={e => setAddStudentId(e.target.value)} type="number" /></div>
                    <button onClick={() => handleAddStudent(selClass.id)} className="btn-primary text-xs">添加</button>
                    <Link href="/" className="text-xs text-gray-400 ml-2">如学生未注册，先去注册</Link>
                  </div>
                </div>

                {/* 班级成员列表 */}
                <div className="card">
                  <h4 className="font-semibold mb-3">👥 班级成员</h4>
                  <table className="w-full text-sm">
                    <thead><tr className="border-b text-gray-500">
                      <th className="text-left py-3 px-2">姓名</th><th className="text-left py-3 px-2">学号</th>
                      <th className="text-left py-3 px-2">加入方式</th><th className="text-left py-3 px-2">加入时间</th>
                      <th className="text-center py-3 px-2">操作</th>
                    </tr></thead>
                    <tbody>
                      {selClass.students?.map((s: any) => (
                        <tr key={s.id} className="border-b hover:bg-gray-50">
                          <td className="py-3 px-2 font-medium">{s.name}</td>
                          <td className="py-3 px-2">{s.student_id}</td>
                          <td className="py-3 px-2">{s.joined_via === "invite" ? "邀请码" : "手动添加"}</td>
                          <td className="py-3 px-2 text-xs text-gray-400">{s.joined_at ? new Date(s.joined_at).toLocaleDateString("zh-CN") : "-"}</td>
                          <td className="py-3 px-2 text-center">
                            <button onClick={() => handleRemoveStudent(selClass.id, s.id)} className="text-xs text-red-500 hover:underline">移出</button>
                          </td>
                        </tr>
                      ))}
                      {(!selClass.students || selClass.students.length === 0) && <tr><td colSpan={5} className="text-center py-8 text-gray-400">暂无成员</td></tr>}
                    </tbody>
                  </table>
                </div>
              </div>
            )}
          </>
        )}
      </main>
    </div>
  );
}

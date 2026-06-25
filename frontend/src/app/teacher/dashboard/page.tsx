"use client";
import { useState, useEffect } from "react";
import Link from "next/link";
import axios from "axios";
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Cell } from "recharts";
import { useToast } from "@/app/toast";
import { TableSkeleton, CardSkeleton } from "@/app/skeleton";

type Tab = "overview" | "errors" | "students" | "student" | "kp" | "classes" | "photo";

export default function TeacherDashboard() {
  const { toast } = useToast();
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
  const [classList, setClassList] = useState<any[]>([]);
  const [selClass, setSelClass] = useState<any>(null);
  const [showCreateClass, setShowCreateClass] = useState(false);
  const [newClassName, setNewClassName] = useState("");
  const [newClassLevel, setNewClassLevel] = useState("初中");
  const [addStudentId, setAddStudentId] = useState("");
  const [inviteCodes, setInviteCodes] = useState<any[]>([]);

  // 拍照批改状态
  const [photoFile, setPhotoFile] = useState<File | null>(null);
  const [photoPreview, setPhotoPreview] = useState<string | null>(null);
  const [photoTitle, setPhotoTitle] = useState("");
  const [photoClassId, setPhotoClassId] = useState<number>(0);
  const [photoUploading, setPhotoUploading] = useState(false);
  const [photoStatusMsg, setPhotoStatusMsg] = useState("");
  const [photoResult, setPhotoResult] = useState<any>(null);
  const [photoHistory, setPhotoHistory] = useState<any[]>([]);

  const headers = () => ({ Authorization: `Bearer ${localStorage.getItem("token")}` });

  const handleDeleteSelf = async () => {
    if (!confirm("确定要删除自己的教师账号吗？此操作不可恢复。")) return;
    setDeletingSelf(true);
    try {
      await axios.delete("/api/auth/teacher/me", { headers: headers() });
      localStorage.clear();
      window.location.href = "/";
    } catch (e: any) {
      toast("删除失败：" + (e.response?.data?.detail || e.message), "error");
    } finally { setDeletingSelf(false); }
  };

  useEffect(() => {
    const t = localStorage.getItem("token");
    if (!t || localStorage.getItem("userType") !== "teacher") { setLoading(false); return; }
    const h = { Authorization: `Bearer ${t}` };
    let completed = 0;
    const allDone = () => { if (++completed >= 3) setLoading(false); };
    axios.get("/api/teacher/dashboard", { headers: h }).then(r => setData(r.data)).catch(() => {}).finally(allDone);
    axios.get("/api/teacher/errors", { headers: h }).then(r => setErrors(r.data)).catch(() => {}).finally(allDone);
    axios.get("/api/teacher/students", { headers: h }).then(r => setStudentList(r.data.students || r.data)).catch(() => {}).finally(allDone);
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
    if (!confirm(`确定删除「${name}」？不可恢复。`)) return;
    setDeletingId(id);
    try {
      await axios.delete(`/api/teacher/students/${id}`, { headers: headers() });
      // 重新加载所有数据（总览/列表/错题都同步更新）
      const [d, e, s] = await Promise.all([
        axios.get("/api/teacher/dashboard", { headers: headers() }).then(r => setData(r.data)).catch(() => {}),
        axios.get("/api/teacher/errors", { headers: headers() }).then(r => setErrors(r.data)).catch(() => {}),
        axios.get("/api/teacher/students", { headers: headers() }).then(r => setStudentList(r.data.students || r.data)).catch(() => {}),
      ]);
    } catch (e: any) { toast("删除失败：" + (e.response?.data?.detail || e.message), "error"); }
    finally { setDeletingId(null); }
  };

  const loadClasses = async () => { try { setClassList((await axios.get("/api/classes", { headers: headers() })).data); } catch {} };
  const loadClassDetail = async (id: number) => {
    try {
      const [cr, ir] = await Promise.all([
        axios.get(`/api/classes/${id}`, { headers: headers() }),
        axios.get(`/api/classes/${id}/invite-codes`, { headers: headers() }),
      ]);
      setSelClass(cr.data); setInviteCodes(ir.data);
    } catch {}
  };
  const handleCreateClass = async () => {
    if (!newClassName.trim()) return;
    try {
      await axios.post("/api/classes", { name: newClassName, school_level: newClassLevel }, { headers: headers() });
      setNewClassName(""); setShowCreateClass(false); loadClasses();
    } catch (e: any) { toast("创建失败：" + (e.response?.data?.detail || e.message), "error"); }
  };
  const handleGenerateCode = async (classId: number) => {
    try { const r = await axios.post(`/api/classes/${classId}/invite-codes`, {}, { headers: headers() }); setInviteCodes(prev => [r.data, ...prev]); }
    catch (e: any) { toast("生成失败：" + (e.response?.data?.detail || e.message), "error"); }
  };
  const handleAddStudent = async (classId: number) => {
    if (!addStudentId.trim()) return;
    try {
      await axios.post(`/api/classes/${classId}/students`, { student_id: parseInt(addStudentId) }, { headers: headers() });
      setAddStudentId(""); loadClassDetail(classId);
    } catch (e: any) { toast("添加失败：" + (e.response?.data?.detail || e.message), "error"); }
  };
  const handleRemoveStudent = async (classId: number, studentId: number) => {
    if (!confirm("确定移出该学生？")) return;
    try { await axios.delete(`/api/classes/${classId}/students/${studentId}`, { headers: headers() }); loadClassDetail(classId); }
    catch (e: any) { toast("操作失败：" + (e.response?.data?.detail || e.message), "error"); }
  };
  const openClassTab = () => { setTab("classes"); loadClasses(); };

  // 拍照批改
  const openPhotoTab = async () => {
    setTab("photo");
    setPhotoResult(null);
    loadClasses();
    try {
      const r = await axios.get("/api/teacher/homework-photo/list", { headers: headers() });
      setPhotoHistory(r.data);
    } catch {}
  };

  const handlePhotoUpload = async () => {
    if (!photoFile) return;
    setPhotoUploading(true);
    setPhotoStatusMsg("上传中...");
    setPhotoResult(null);
    try {
      const fd = new FormData();
      fd.append("file", photoFile);
      fd.append("title", photoTitle || "拍照批改");
      if (photoClassId) fd.append("class_id", String(photoClassId));

      const res = await axios.post("/api/teacher/homework-photo/upload", fd, { headers: { ...headers(), "Content-Type": "multipart/form-data" } });
      const pid = res.data.id;
      setPhotoStatusMsg("AI 正在批改中，请稍候...");

      let attempts = 0;
      while (attempts < 60) {
        await new Promise(resolve => setTimeout(resolve, 3000));
        attempts++;
        const elapsed = attempts * 3;
        if (elapsed < 30) setPhotoStatusMsg(`⏳ AI 批改中... ${elapsed}s`);
        else if (elapsed < 60) setPhotoStatusMsg(`⏳ 识别题目中... ${elapsed}s`);
        else setPhotoStatusMsg(`⏳ 还在批改... ${elapsed}s`);

        const statusRes = await axios.get(`/api/teacher/homework-photo/${pid}/status`, { headers: headers() });
        if (statusRes.data.status === "done") {
          setPhotoResult(statusRes.data.result);
          setPhotoStatusMsg("");
          setPhotoFile(null); setPhotoPreview(null);
          // 刷新历史
          const r = await axios.get("/api/teacher/homework-photo/list", { headers: headers() });
          setPhotoHistory(r.data);
          setPhotoUploading(false);
          return;
        }
        if (statusRes.data.status === "error") {
          throw new Error(statusRes.data.error || "批改失败");
        }
      }
      throw new Error("批改超时（3 分钟），请稍后在历史记录中查看");
    } catch (e: any) {
      toast("上传失败：" + (e.response?.data?.detail || e.message), "error");
    } finally { setPhotoUploading(false); setPhotoStatusMsg(""); }
  };

  const viewPhotoResult = async (id: number) => {
    try {
      const r = await axios.get(`/api/teacher/homework-photo/${id}/result`, { headers: headers() });
      setPhotoResult(r.data);
    } catch (e: any) { toast("加载失败", "error"); }
  };

  if (loading) return <div className="min-h-screen flex items-center justify-center"><div className="spinner spinner-lg"></div></div>;

  const TABS: { key: Tab; label: string }[] = [
    { key: "overview", label: "📊 总览" },
    { key: "errors", label: "❌ 错题汇总" },
    { key: "students", label: "👥 学生列表" },
    { key: "classes", label: "🏫 班级管理" },
    { key: "photo", label: "📷 拍照批改" },
  ];

  return (
    <div className="min-h-screen bg-gray-50">
      {/* 导航栏 */}
      <div className="navbar">
        <div className="max-w-7xl mx-auto px-6 h-14 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <span className="text-xl">📐</span>
            <span className="font-bold text-lg">数学教学智能体 · 教师端</span>
          </div>
          <div className="flex items-center gap-4">
            <Link href="/teacher/assignments" className="text-sm text-indigo-600 hover:text-indigo-800 font-medium">📋 发布作业</Link>
            <button onClick={() => { localStorage.clear(); window.location.href = "/"; }}
              className="btn-secondary btn-sm">退出</button>
            <button onClick={handleDeleteSelf} disabled={deletingSelf}
              className="btn-danger btn-sm">{deletingSelf ? "删除中..." : "注销账号"}</button>
          </div>
        </div>
      </div>

      {/* Tabs */}
      <div className="max-w-7xl mx-auto px-6">
        <div className="tabs">
          {TABS.map(t => (
            <button key={t.key} onClick={t.key === "classes" ? openClassTab : t.key === "photo" ? openPhotoTab : () => setTab(t.key)}
              className={`tab ${tab === t.key ? "active" : ""}`}>{t.label}</button>
          ))}
          {tab === "student" && <span className="tab active">👤 {selStudent?.name}</span>}
          {tab === "kp" && <span className="tab active">📖 {kpData?.knowledge_point}</span>}
        </div>
      </div>

      <main className="max-w-7xl mx-auto px-6 py-8">
        {/* 总览 */}
        {tab === "overview" && (
          <>
            <div className="grid grid-cols-4 gap-4 mb-8">
              <div className="stat-card"><div className="value text-indigo-600">{data?.total_students||0}</div><div className="label">👥 学生总数</div></div>
              <div className="stat-card"><div className="value text-green-600">{data?.total_homework||0}</div><div className="label">📄 作业提交</div></div>
              <div className="stat-card"><div className="value text-indigo-500">{data?.total_exams||0}</div><div className="label">📝 考试次数</div></div>
              <div className="stat-card"><div className="value text-amber-500">{data?.class_avg_score||0}</div><div className="label">📊 班级均分</div></div>
            </div>
            <div className="card">
              <h3 className="font-semibold mb-4">⚠️ 需关注学生</h3>
              {data?.top_error_students?.length > 0 ? (
                <div className="table-wrap">
                  <table className="w-full">
                    <thead><tr><th>#</th><th className="text-left">姓名</th><th>薄弱知识点</th><th>错题数</th></tr></thead>
                    <tbody>{data.top_error_students.map((s: any, i: number) => (
                      <tr key={s.student_id} className="cursor-pointer" onClick={() => viewStudent(s.student_id)}>
                        <td className="text-center text-gray-400">{i+1}</td>
                        <td className="font-medium">{s.name}</td>
                        <td className="text-center"><span className="badge badge-warning">{s.weak_points} 个</span></td>
                        <td className="text-center"><span className="badge badge-danger">{s.total_errors}</span></td>
                      </tr>
                    ))}</tbody>
                  </table>
                </div>
              ) : <div className="empty-state"><div className="icon">✅</div><div className="text">暂无需要关注的学生</div></div>}
            </div>
          </>
        )}

        {/* 错题汇总 */}
        {tab === "errors" && (
          <>
            <div className="card mb-6"><h3 className="font-semibold mb-4">📊 全班知识点错误率</h3>
              {errors.length > 0 ? (
                <ResponsiveContainer width="100%" height={300}>
                  <BarChart data={errors.slice(0, 10)}>
                    <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" />
                    <XAxis dataKey="knowledge_point" tick={{fontSize:12}} interval={0} angle={-25} textAnchor="end" height={80} />
                    <YAxis /><Tooltip />
                    <Bar dataKey="error_rate" fill="#ef4444" radius={[6,6,0,0]} />
                  </BarChart>
                </ResponsiveContainer>
              ) : <div className="empty-state"><div className="icon">📊</div><div className="text">暂无错题记录</div></div>}
            </div>
            <div className="card"><h3 className="font-semibold mb-4">📋 知识点明细</h3>
              {errors.map((e, i) => (
                <div key={i} className="flex items-center justify-between p-4 border-b border-gray-50 last:border-0 hover:bg-gray-50 rounded-lg cursor-pointer"
                  onClick={() => viewKP(e.knowledge_point)}>
                  <div><div className="font-medium">{e.knowledge_point}</div>
                    <div className="text-xs text-gray-400 mt-0.5">{e.affected_students}人 · 错误率 {e.error_rate}%</div></div>
                  <span className="badge badge-danger">{e.error_count} 次</span>
                </div>
              ))}
              {errors.length === 0 && <div className="empty-state"><div className="icon">📋</div><div className="text">暂无错题记录</div></div>}
            </div>
          </>
        )}

        {/* 学生列表 */}
        {tab === "students" && (
          <div className="card">
            <h3 className="font-semibold mb-4">👥 学生列表 <span className="text-gray-400 text-sm font-normal">（共 {studentList.length} 人）</span></h3>
            {studentList.length > 0 ? (
              <div className="table-wrap">
                <table className="w-full">
                  <thead><tr><th>姓名</th><th>学号</th><th>学段</th><th>作业</th><th>考试</th><th>均分</th><th>错题</th><th>最近活动</th><th>操作</th></tr></thead>
                  <tbody>{studentList.map((s: any) => (
                    <tr key={s.id}>
                      <td className="font-medium">{s.name}</td>
                      <td className="text-gray-500">{s.student_id}</td>
                      <td><span className="badge badge-gray">{s.level}</span></td>
                      <td className="text-center">{s.homework_count}</td>
                      <td className="text-center">{s.exam_count}</td>
                      <td className="text-center font-semibold">{s.avg_score}</td>
                      <td className="text-center"><span className="badge badge-danger">{s.error_count}</span></td>
                      <td className="text-center text-xs text-gray-400">{s.last_login ? new Date(s.last_login).toLocaleDateString("zh-CN") : "未登录"}</td>
                      <td className="text-center">
                        <button onClick={() => viewStudent(s.id)} className="btn-secondary btn-sm mr-1">详情</button>
                        <button onClick={() => handleDeleteStudent(s.id, s.name)} disabled={deletingId === s.id}
                          className="btn-danger btn-sm">{deletingId === s.id ? "..." : "删除"}</button>
                      </td>
                    </tr>
                  ))}</tbody>
                </table>
              </div>
            ) : <div className="empty-state"><div className="icon">👥</div><div className="text">暂无学生，请先创建班级并邀请学生</div></div>}
          </div>
        )}

        {/* 学生错题详情 */}
        {tab === "student" && (
          <div>
            <button onClick={() => setTab("students")} className="text-indigo-600 text-sm mb-4 font-medium">← 返回学生列表</button>
            {selStudent && <div className="card mb-4 flex items-center gap-3"><span className="text-2xl">👤</span><div><h3 className="font-semibold text-lg">{selStudent.name}</h3><span className="text-sm text-gray-500">{selStudent.level}</span></div></div>}
            {stErrors.length > 0 ? stErrors.map((e, i) => (
              <div key={i} className="card mb-3 p-4 border-l-4 border-l-red-400">
                <div className="font-medium text-red-800 mb-1">{e.knowledge_point}</div>
                <div className="text-sm text-gray-600 mb-2">{e.question}</div>
                <div className="flex gap-4 text-xs"><span className="text-red-500">答：{e.student_answer}</span><span className="text-green-600">✓ {e.correct_answer}</span></div>
              </div>
            )) : <div className="empty-state"><div className="icon">🎉</div><div className="text">暂无错题</div></div>}
          </div>
        )}

        {/* 知识点钻取 */}
        {tab === "kp" && kpData && (
          <div>
            <button onClick={() => setTab("errors")} className="text-indigo-600 text-sm mb-4 font-medium">← 返回</button>
            <div className="card mb-4"><h3 className="font-semibold">{kpData.knowledge_point}</h3><span className="text-xs text-gray-400">共 {kpData.total_errors} 条记录</span></div>
            {kpData.errors?.map((e: any, i: number) => (
              <div key={i} className="card mb-3 p-4">
                <span className="font-medium text-indigo-600">{e.student_name}</span>
                <div className="text-sm mt-1">{e.question}</div>
                <div className="flex gap-4 text-xs mt-1"><span className="text-red-500">答：{e.student_answer}</span><span className="text-green-600">✓ {e.correct_answer}</span></div>
              </div>
            ))}
            {(!kpData.errors || kpData.errors.length === 0) && <div className="empty-state"><div className="icon">📖</div><div className="text">暂无错题</div></div>}
          </div>
        )}

        {/* 班级管理 */}
        {tab === "classes" && (
          <>
            <div className="flex items-center justify-between mb-6">
              <h2 className="text-xl font-bold">🏫 班级管理</h2>
              <button onClick={() => setShowCreateClass(true)} className="btn-primary btn-sm">+ 创建班级</button>
            </div>

            {showCreateClass && (
              <div className="card mb-6 bg-gradient-to-r from-indigo-50 to-white border-indigo-100">
                <h3 className="font-semibold mb-4 text-indigo-800">✨ 创建新班级</h3>
                <div className="flex flex-wrap gap-4 items-end">
                  <div><label className="block text-xs font-medium text-gray-600 mb-1">班级名称</label>
                    <input className="input !w-48" value={newClassName} onChange={e => setNewClassName(e.target.value)} placeholder="例：初二(3)班" /></div>
                  <div><label className="block text-xs font-medium text-gray-600 mb-1">学段</label>
                    <select className="input !w-32" value={newClassLevel} onChange={e => setNewClassLevel(e.target.value)}>
                      <option value="小学">小学</option><option value="初中">初中</option><option value="高中">高中</option>
                    </select></div>
                  <button onClick={handleCreateClass} className="btn-primary btn-sm">✅ 确认</button>
                  <button onClick={() => setShowCreateClass(false)} className="btn-secondary btn-sm">取消</button>
                </div>
              </div>
            )}

            {!selClass ? (
              <>
                {classList.length > 0 ? (
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                    {classList.map((c: any) => (
                      <div key={c.id} className="card card-hover" onClick={() => loadClassDetail(c.id)}>
                        <div className="flex items-center gap-3 mb-2">
                          <span className="text-2xl">🏫</span>
                          <div><div className="font-semibold text-lg">{c.name}</div>
                            <div className="text-xs text-gray-400">{c.school_level} · {new Date(c.created_at).toLocaleDateString("zh-CN")} 创建</div></div>
                        </div>
                        <div className="flex items-center gap-3 mt-3 pt-3 border-t border-gray-50">
                          <span className="badge badge-primary">{c.student_count} 名学生</span>
                        </div>
                      </div>
                    ))}
                  </div>
                ) : (
                  <div className="empty-state"><div className="icon">🏫</div><div className="text">还没有班级，点击上方创建</div></div>
                )}
              </>
            ) : (
              <div>
                <button onClick={() => { setSelClass(null); loadClasses(); }} className="text-indigo-600 text-sm mb-4 font-medium">← 返回班级列表</button>

                <div className="card mb-6 bg-gradient-to-r from-indigo-50 to-white">
                  <div className="flex items-center justify-between flex-wrap gap-4">
                    <div><h3 className="text-xl font-bold">{selClass.name}</h3>
                      <span className="text-sm text-gray-500">{selClass.school_level} · {selClass.student_count} 名学生</span></div>
                    <button onClick={() => handleGenerateCode(selClass.id)} className="btn-primary btn-sm">🔑 生成邀请码</button>
                  </div>

                  {inviteCodes.length > 0 && (
                    <div className="mt-4 pt-4 border-t border-indigo-100">
                      <h4 className="text-sm font-semibold mb-2 text-gray-700">🔑 邀请码</h4>
                      <div className="flex flex-wrap gap-2">
                        {inviteCodes.map((c: any) => (
                          <div key={c.id} className={`inline-flex items-center gap-2 px-3 py-1.5 rounded-lg text-sm font-mono border
                            ${c.is_active ? 'bg-green-50 border-green-200' : 'bg-gray-50 border-gray-200 opacity-60'}`}>
                            <span className={`font-bold ${c.is_active ? 'text-green-800' : 'text-gray-400'}`}>{c.code}</span>
                            {c.is_active && (
                              <button className="text-xs text-gray-400 hover:text-indigo-600"
                                onClick={() => navigator.clipboard.writeText(c.code).then(() => { toast("已复制", "info"); })}>
                                📋
                              </button>
                            )}
                            <span className="text-xs text-gray-400">{c.used_count}/{c.max_used_count || '∞'}</span>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}

                  <div className="mt-4 pt-4 border-t border-indigo-100">
                    <div className="flex gap-2 items-end flex-wrap">
                      <div><label className="block text-xs font-medium text-gray-600 mb-1">手动添加学生（输入学生 ID）</label>
                        <input className="input !w-40" placeholder="学生 ID" value={addStudentId} onChange={e => setAddStudentId(e.target.value)} type="number" /></div>
                      <button onClick={() => handleAddStudent(selClass.id)} className="btn-primary btn-sm">添加</button>
                    </div>
                  </div>
                </div>

                <div className="card">
                  <h4 className="font-semibold mb-4">👥 班级成员（{selClass.students?.length || 0} 人）</h4>
                  {selClass.students?.length > 0 ? (
                    <div className="table-wrap">
                      <table className="w-full">
                        <thead><tr><th>姓名</th><th>学号</th><th>加入方式</th><th>加入时间</th><th>操作</th></tr></thead>
                        <tbody>{selClass.students.map((s: any) => (
                          <tr key={s.id}>
                            <td className="font-medium">{s.name}</td>
                            <td className="text-gray-500">{s.student_id}</td>
                            <td><span className={`badge ${s.joined_via === "invite" ? "badge-primary" : "badge-gray"}`}>{s.joined_via === "invite" ? "邀请码" : "手动添加"}</span></td>
                            <td className="text-xs text-gray-400">{s.joined_at ? new Date(s.joined_at).toLocaleDateString("zh-CN") : "-"}</td>
                            <td><button onClick={() => handleRemoveStudent(selClass.id, s.id)} className="btn-danger btn-sm">移出</button></td>
                          </tr>
                        ))}</tbody>
                      </table>
                    </div>
                  ) : <div className="empty-state"><div className="icon">👥</div><div className="text">暂无成员</div></div>}
                </div>
              </div>
            )}
          </>
        )}

        {/* 拍照批改 */}
        {tab === "photo" && (
          <div>
            {!photoResult ? (
              <>
                <div className="card mb-6">
                  <h3 className="font-semibold mb-4">📷 上传作业照片</h3>
                  <div className="border-2 border-dashed rounded-xl p-10 text-center border-gray-200">
                    <div className="text-4xl mb-3">📷</div>
                    <p className="text-gray-500 mb-2">支持 JPG、PNG 格式，拍摄学生作业</p>
                    <input type="file" accept="image/*" capture="environment" onChange={e => {
                      const f = e.target.files?.[0];
                      if (f) { setPhotoFile(f); setPhotoPreview(URL.createObjectURL(f)); }
                    }} className="block mx-auto" />
                    {photoPreview && <img src={photoPreview} alt="preview" className="max-h-64 mx-auto mt-4 rounded-lg shadow" />}
                  </div>
                </div>
                <div className="card mb-6 space-y-4">
                  <div>
                    <label className="block text-sm font-medium mb-1.5">作业标题</label>
                    <input className="input" placeholder="例：第三章课后练习" value={photoTitle} onChange={e => setPhotoTitle(e.target.value)} />
                  </div>
                  <div>
                    <label className="block text-sm font-medium mb-1.5">关联班级 <span className="text-gray-400 font-normal">（选填，可自动记录错题到学生）</span></label>
                    <select className="input" value={photoClassId} onChange={e => setPhotoClassId(Number(e.target.value))}>
                      <option value={0}>不关联班级</option>
                      {classList.map((c: any) => (
                        <option key={c.id} value={c.id}>🏫 {c.name}</option>
                      ))}
                    </select>
                  </div>
                </div>
                <button onClick={handlePhotoUpload} disabled={!photoFile || photoUploading} className="btn-primary w-full text-lg py-3">
                  {photoUploading ? (photoStatusMsg || "AI 批改中...") : "🤖 开始批改"}
                </button>
                {photoUploading && (
                  <div className="mt-4">
                    <div className="w-full bg-gray-200 rounded-full h-2"><div className="bg-indigo-500 h-2 rounded-full animate-pulse" style={{ width: "60%" }} /></div>
                    <p className="text-gray-400 text-sm mt-2 text-center">请勿关闭页面</p>
                  </div>
                )}
              </>
            ) : (
              <div className="space-y-6">
                <button onClick={() => setPhotoResult(null)} className="text-indigo-600 text-sm font-medium">← 继续上传</button>
                <div className="card">
                  <h3 className="font-semibold text-lg mb-4">📊 批改结果</h3>
                  <div className="text-4xl font-bold text-center text-indigo-600 mb-4">{photoResult.score}分</div>
                  {photoResult.total_count > 0 && <p className="text-center text-sm text-gray-500 mb-2">正确 {photoResult.correct_count}/{photoResult.total_count} 题</p>}
                  {photoResult.comments && <div className="p-4 bg-indigo-50 rounded-lg mb-4"><p className="text-indigo-800">{photoResult.comments}</p></div>}
                </div>
                {photoResult.wrong_questions?.filter((q: any) => !q.correct).map((q: any, i: number) => (
                  <div key={i} className="card p-4 bg-red-50">
                    <div className="font-medium mb-1">{q.question}</div>
                    {q.student_answer && <div className="text-sm text-red-600">学生答案：{q.student_answer}</div>}
                    {q.correct_answer && <div className="text-sm text-green-600">正确答案：{q.correct_answer}</div>}
                    {q.explanation && <div className="text-sm text-gray-700 mt-2">💡 {q.explanation}</div>}
                  </div>
                ))}
              </div>
            )}

            {/* 历史记录 */}
            <div className="mt-8">
              <h3 className="font-semibold mb-4">📋 批改历史</h3>
              {photoHistory.length > 0 ? (
                <div className="space-y-3">
                  {photoHistory.map((p: any) => (
                    <div key={p.id} className="card flex items-center justify-between cursor-pointer hover:shadow-md transition-shadow" onClick={() => viewPhotoResult(p.id)}>
                      <div className="flex items-center gap-3">
                        <span className="text-2xl">📷</span>
                        <div>
                          <div className="font-medium">{p.title}</div>
                          <div className="text-xs text-gray-400">{p.class_name || "未关联班级"} · {new Date(p.created_at).toLocaleDateString("zh-CN")}</div>
                        </div>
                      </div>
                      <div className="text-right">
                        {p.status === "done" ? (
                          <span className="text-lg font-bold text-indigo-600">{p.score}分</span>
                        ) : p.status === "error" ? (
                          <span className="badge badge-danger">失败</span>
                        ) : (
                          <span className="badge badge-warning">批改中</span>
                        )}
                      </div>
                    </div>
                  ))}
                </div>
              ) : (
                <div className="empty-state"><div className="icon">📷</div><div className="text">暂无批改记录，上传第一张作业照片吧</div></div>
              )}
            </div>
          </div>
        )}
      </main>
    </div>
  );
}

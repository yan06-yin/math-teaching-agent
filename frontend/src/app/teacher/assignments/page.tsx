"use client";
import { useState, useEffect, useRef } from "react";
import Link from "next/link";
import axios from "axios";

export default function TeacherAssignments() {
  const [mode, setMode] = useState<"list" | "create">("list");
  const [assignments, setAssignments] = useState<any[]>([]);
  const [title, setTitle] = useState("");
  const [desc, setDesc] = useState("");
  const [questions, setQuestions] = useState<string[]>([""]);
  const [classId, setClassId] = useState<number>(0);
  const [classList, setClassList] = useState<any[]>([]);
  const [loading, setLoading] = useState(false);
  const [loaded, setLoaded] = useState(false);
  const [photoFile, setPhotoFile] = useState<File | null>(null);
  const [photoPreview, setPhotoPreview] = useState<string | null>(null);
  const photoPreviewUrlRef = useRef<string | null>(null);

  // 卸载时释放 blob URL，避免内存泄漏
  useEffect(() => {
    return () => {
      if (photoPreviewUrlRef.current) URL.revokeObjectURL(photoPreviewUrlRef.current);
    };
  }, []);

  const headers = () => ({ Authorization: `Bearer ${typeof window !== "undefined" ? localStorage.getItem("token") : ""}` });

  useEffect(() => {
    if (!localStorage.getItem("token")) { window.location.href = "/"; return; }
    if (!loaded && !loading) {
      loadAssignments();
      loadClasses();
    }
  }, []);

  const loadAssignments = async () => {
    setLoading(true);
    try {
      const r = await axios.get("/api/assignments/teacher", { headers: headers() });
      setAssignments(r.data);
    } catch (e) {} finally {
      setLoading(false);
      setLoaded(true);
    }
  };
  const loadClasses = async () => {
    try {
      const r = await axios.get("/api/classes", { headers: headers() });
      setClassList(r.data);
    } catch {}
  };

  const addQuestion = () => setQuestions([...questions, ""]);
  const updateQ = (i: number, v: string) => {
    const q = [...questions]; q[i] = v; setQuestions(q);
  };

  const createAssignment = async () => {
    setLoading(true);
    try {
      const fd = new FormData();
      fd.append("title", title);
      fd.append("description", desc);
      if (classId) fd.append("class_id", String(classId));
      const qs = questions.filter(q => q.trim()).map((q, i) => ({ id: i + 1, question: q, answer: "" }));
      fd.append("questions", JSON.stringify(qs));
      if (photoFile) fd.append("photo", photoFile);

      await axios.post("/api/assignments/teacher", fd, {
        // 不要手动设置 Content-Type：axios 传 FormData 时会自动生成含 boundary 的正确值
        headers: { ...headers() },
      });
      setTitle(""); setDesc(""); setQuestions([""]); setClassId(0);
      setPhotoFile(null); setPhotoPreview(null);
      setMode("list");
      loadAssignments();
    } catch (e: any) {
      alert("发布失败：" + (e.response?.data?.detail || e.message));
    }
    setLoading(false);
  };

  return (
    <div className="min-h-screen bg-gray-50">
      <div className="navbar">
        <div className="max-w-4xl mx-auto h-14 flex items-center justify-between px-6">
          <Link href="/teacher/dashboard" className="text-sm text-indigo-600 font-medium">← 返回</Link>
          <span className="font-semibold">📋 作业管理</span>
          <button onClick={() => { setMode(mode === "list" ? "create" : "list"); loadClasses(); }}
            className="btn-secondary btn-sm">
            {mode === "list" ? "+ 发布新作业" : "← 返回列表"}
          </button>
        </div>
      </div>
      <main className="max-w-4xl mx-auto px-6 py-8">
        {mode === "list" ? (
          <>
            <h2 className="text-xl font-bold mb-6">📋 已发布的作业</h2>
            <div className="space-y-3">
              {assignments.map((a: any) => (
                <div key={a.id} className="card">
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-3">
                      {a.photo_url ? <span className="text-2xl">📷</span> : <span className="text-2xl">📝</span>}
                      <div>
                        <div className="font-semibold text-lg">{a.title}</div>
                        <div className="text-sm text-gray-500 mt-0.5">{a.description}</div>
                      </div>
                    </div>
                    <span className="badge badge-gray">{a.class_name || "📢 广播"}</span>
                  </div>
                  <div className="text-xs text-gray-400 mt-2">
                    {a.photo_url && "📷 拍照作业 · "}
                    {a.questions_count > 0 && `${a.questions_count} 道题 · `}
                    {a.submissions} 人已提交
                  </div>
                </div>
              ))}
              {assignments.length === 0 && <div className="empty-state"><div className="icon">📋</div><div className="text">暂无作业</div></div>}
            </div>
          </>
        ) : (
          <div className="card max-w-2xl mx-auto">
            <h2 className="text-xl font-bold mb-6">📝 发布新作业</h2>
            <div className="space-y-4">
              <div>
                <label className="block text-sm font-medium mb-1.5">作业标题</label>
                <input className="input" value={title} onChange={e => setTitle(e.target.value)} placeholder="例：第三章课后练习" />
              </div>
              <div>
                <label className="block text-sm font-medium mb-1.5">描述</label>
                <textarea className="input min-h-[80px]" value={desc} onChange={e => setDesc(e.target.value)} placeholder="请在周五前完成" />
              </div>
              <div>
                <label className="block text-sm font-medium mb-1.5">发布到班级</label>
                <select className="input" value={classId} onChange={e => setClassId(Number(e.target.value))}>
                  <option value={0}>📢 广播（所有学生可见）</option>
                  {classList.map((c: any) => (
                    <option key={c.id} value={c.id}>🏫 {c.name}</option>
                  ))}
                </select>
              </div>

              {/* 拍照上传 */}
              <div className="border-2 border-dashed rounded-xl p-6 text-center border-gray-200 bg-gray-50">
                <div className="text-3xl mb-2">📷</div>
                <p className="text-gray-500 text-sm mb-2">拍照布置作业（选填）</p>
                <p className="text-gray-400 text-xs mb-3">学生将直接看到这张照片，然后在线提交答案</p>
                <input type="file" accept="image/*" capture="environment" onChange={e => {
                  const f = e.target.files?.[0];
                  if (f) {
                    // 释放旧的 blob URL，避免内存泄漏
                    if (photoPreviewUrlRef.current) URL.revokeObjectURL(photoPreviewUrlRef.current);
                    const url = URL.createObjectURL(f);
                    photoPreviewUrlRef.current = url;
                    setPhotoFile(f);
                    setPhotoPreview(url);
                  }
                }} className="block mx-auto text-sm" />
                {photoPreview && (
                  <div className="mt-3 relative inline-block">
                    <img src={photoPreview} alt="preview" className="max-h-48 mx-auto rounded-lg shadow" />
                    <button onClick={() => {
                      if (photoPreviewUrlRef.current) { URL.revokeObjectURL(photoPreviewUrlRef.current); photoPreviewUrlRef.current = null; }
                      setPhotoFile(null); setPhotoPreview(null);
                    }}
                      className="absolute -top-2 -right-2 w-6 h-6 bg-red-500 text-white rounded-full text-xs flex items-center justify-center">✕</button>
                  </div>
                )}
              </div>

              {/* 文字题目 */}
              <div>
                <label className="block text-sm font-medium mb-1.5">在线题目（选填，和照片可同时使用）</label>
                {questions.map((q, i) => (
                  <div key={i} className="flex gap-2 mb-2">
                    <span className="mt-2.5 text-sm font-medium w-6">{i+1}.</span>
                    <input className="input flex-1" value={q} onChange={e => updateQ(i, e.target.value)} placeholder={`第${i+1}题`} />
                  </div>
                ))}
                <button onClick={addQuestion} className="text-sm text-indigo-600 mt-1 font-medium">+ 添加题目</button>
              </div>

              <button onClick={createAssignment} disabled={loading || !title.trim()}
                className="btn-primary w-full mt-4">
                {loading ? "发布中..." : "📢 发布作业"}
              </button>
            </div>
          </div>
        )}
      </main>
    </div>
  );
}

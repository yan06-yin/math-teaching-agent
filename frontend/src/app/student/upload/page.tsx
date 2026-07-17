"use client";
import { useState, useEffect, useRef } from "react";
import Link from "next/link";
import axios from "axios";

export default function UploadPage() {
  const [file, setFile] = useState<File | null>(null);
  const [preview, setPreview] = useState<string | null>(null);
  const [manualInput, setManualInput] = useState("");
  const [subject, setSubject] = useState("math");
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<any>(null);
  const [statusMsg, setStatusMsg] = useState("");
  const [errorMsg, setErrorMsg] = useState("");
  // 持有当前 preview 的 object URL，便于更换/卸载时 revoke，避免 Blob 内存泄漏
  const previewUrlRef = useRef<string | null>(null);
  // 标记组件是否仍挂载，避免轮询中在已卸载组件上 setState
  const isMountedRef = useRef(true);

  useEffect(() => {
    if (!localStorage.getItem("token")) { window.location.href = "/"; }
    return () => {
      isMountedRef.current = false;
      // 卸载时释放 blob URL
      if (previewUrlRef.current) URL.revokeObjectURL(previewUrlRef.current);
    };
  }, []);

  /** 选择图片：先释放旧的 blob URL，再创建新的 */
  const pickFile = (f: File) => {
    if (previewUrlRef.current) URL.revokeObjectURL(previewUrlRef.current);
    setFile(f);
    const url = URL.createObjectURL(f);
    previewUrlRef.current = url;
    setPreview(url);
  };

  const handleSubmit = async () => {
    if (!file && !manualInput.trim()) return;
    setLoading(true); setResult(null); setStatusMsg("上传中..."); setErrorMsg("");
    try {
      const fd = new FormData();
      if (file) fd.append("file", file);
      if (manualInput.trim()) fd.append("student_answers", manualInput);
      fd.append("subject", subject);
      const token = localStorage.getItem("token");
      const res = await axios.post(`/api/homework/upload`, fd, {
        headers: { Authorization: `Bearer ${token}` },
      });
      const sid = res.data.submission_id;
      setStatusMsg("AI 正在批改中，请稍候...");

      let attempts = 0;
      const maxAttempts = 60;
      while (attempts < maxAttempts && isMountedRef.current) {
        await new Promise(resolve => setTimeout(resolve, 3000));
        if (!isMountedRef.current) return;
        attempts++;
        const elapsed = attempts * 3;
        if (elapsed < 30) setStatusMsg(`⏳ AI 批改中... ${elapsed}s`);
        else if (elapsed < 60) setStatusMsg(`⏳ 识别题目中... ${elapsed}s`);
        else setStatusMsg(`⏳ 还在批改... ${elapsed}s（题目越多越久）`);
        const statusRes = await axios.get(`/api/homework/upload/${sid}/status`, {
          headers: { Authorization: `Bearer ${token}` },
        });
        if (statusRes.data.status === "done") {
          if (!isMountedRef.current) return;
          setResult(statusRes.data.result || statusRes.data);
          setStatusMsg("");
          setLoading(false);
          return;
        }
        if (statusRes.data.status === "error") {
          throw new Error(statusRes.data.error || "批改失败");
        }
      }
      if (!isMountedRef.current) return;
      throw new Error("批改超时（3 分钟），请稍后在作业列表中查看结果");
    } catch (e: any) {
      if (!isMountedRef.current) return;
      setErrorMsg(e.response?.data?.detail || e.message || "上传失败");
    } finally {
      if (isMountedRef.current) { setLoading(false); setStatusMsg(""); }
    }
  };

  return (
    <div className="min-h-screen bg-gray-50">
      <nav className="bg-white border-b px-6 py-4"><div className="max-w-4xl mx-auto flex items-center justify-between"><Link href="/student/dashboard" className="text-[#6366f1] hover:underline text-sm">← 返回首页</Link><span className="font-semibold">拍照批改</span><div /></div></nav>
      <main className="max-w-4xl mx-auto px-6 py-8">
        {!result ? (
          <>
            <div className="card mb-6">
              <h3 className="font-semibold mb-4">选择学科</h3>
              <div className="flex gap-3">
                {[
                  { id: 'math', label: '数学', icon: '📐', color: 'bg-indigo-50 border-indigo-200 text-indigo-700' },
                  { id: 'chinese', label: '语文', icon: '📝', color: 'bg-green-50 border-green-200 text-green-700' },
                  { id: 'english', label: '英语', icon: '🔤', color: 'bg-amber-50 border-amber-200 text-amber-700' },
                ].map(s => (
                  <button key={s.id} onClick={() => setSubject(s.id)}
                    className={`flex-1 py-3 px-4 rounded-xl border-2 text-center transition-all ${subject === s.id ? `${s.color} border-current font-semibold scale-105 shadow-sm` : 'bg-white border-gray-200 text-gray-500 hover:border-gray-300'}`}>
                    <div className="text-2xl mb-1">{s.icon}</div>
                    <div className="text-sm">{s.label}</div>
                  </button>
                ))}
              </div>
            </div>
            <div className="card mb-6">
              <h3 className="font-semibold mb-4">上传作业照片</h3>
              <div className="border-2 border-dashed rounded-xl p-12 text-center border-gray-200">
                <div className="text-4xl mb-3">📷</div>
                <p className="text-gray-500 mb-2">支持 JPG、PNG 格式</p>
                <input type="file" accept="image/*" onChange={e => { const f = e.target.files?.[0]; if (f) pickFile(f); }} className="block mx-auto" />
                {preview && <img src={preview} alt="preview" className="max-h-64 mx-auto mt-4 rounded-lg shadow" />}
              </div>
            </div>
            <div className="card mb-6">
              <h3 className="font-semibold mb-4">或手动输入题目和答案</h3>
              <textarea className="input min-h-[120px]" placeholder="1. 解方程 2x+3=7&#10;答案：x=2" value={manualInput} onChange={e => setManualInput(e.target.value)} />
            </div>
            <button onClick={handleSubmit} disabled={!file && !manualInput.trim() || loading} className="btn-primary w-full text-lg py-3">{loading ? (statusMsg || "AI 正在批改中...") : "🤖 开始批改"}</button>
            {loading && (
              <div className="mt-4">
                <div className="w-full bg-gray-200 rounded-full h-2"><div className="bg-indigo-500 h-2 rounded-full animate-pulse" style={{ width: "60%" }} /></div>
                <p className="text-gray-400 text-sm mt-2 text-center">请勿关闭页面</p>
              </div>
            )}
            {errorMsg && (
              <div className="p-3 bg-red-50 text-red-600 text-sm rounded-lg border border-red-100 mt-4">
                <p>⚠️ {errorMsg}</p>
                <button onClick={handleSubmit} className="mt-2 text-xs text-indigo-600 hover:underline">🔄 重新上传</button>
              </div>
            )}
          </>
        ) : (
          <div className="space-y-6">
            <div className="card">
              <div className="flex items-center justify-between mb-2">
                <h3 className="font-semibold text-lg">批改结果</h3>
                <span className="text-xs px-2 py-1 rounded-full bg-gray-100 text-gray-500">
                  {result.subject === 'chinese' ? '📝 语文' : result.subject === 'english' ? '🔤 英语' : '📐 数学'}
                </span>
              </div>
              <div className="text-4xl font-bold text-center text-[#6366f1] mb-4">{result.score}分</div>
              {(result.total_count ?? 0) > 0 && <p className="text-center text-sm text-gray-500 mb-2">正确 {result.correct_count}/{result.total_count} 题</p>}
              {result.comments && <div className="p-4 bg-[#eef2ff] rounded-lg mb-4"><p className="text-indigo-800">{result.comments}</p></div>}
            </div>
            {result.wrong_questions?.filter((q: any) => !q.correct).map((q: any, i: number) => (
              <div key={i} className="card p-4 bg-red-50">
                <div className="font-medium mb-1">{q.question}</div>
                {q.student_answer && <div className="text-sm text-red-600">你的答案：{q.student_answer}</div>}
                {q.correct_answer && <div className="text-sm text-green-600">正确答案：{q.correct_answer}</div>}
                {q.explanation && <div className="text-sm text-gray-700 mt-2">💡 {q.explanation}</div>}
                {/* 步骤级过程分展示 */}
                {q.step_analysis && q.step_analysis.length > 0 && (
                  <div className="mt-3 pt-3 border-t border-red-200">
                    <div className="text-xs font-semibold text-gray-500 mb-2">📋 步骤分析</div>
                    {q.step_analysis.map((step: any, si: number) => (
                      <div key={si} className={`flex items-center gap-2 text-xs py-1 ${step.status === 'correct' ? 'text-green-700' : step.status === 'partial' ? 'text-amber-700' : 'text-red-700'}`}>
                        <span>{step.status === 'correct' ? '✅' : step.status === 'partial' ? '⚠️' : '❌'}</span>
                        <span className="flex-1">{step.description}</span>
                        {step.feedback && <span className="text-gray-400">({step.feedback})</span>}
                      </div>
                    ))}
                    {q.process_score !== undefined && (
                      <div className="text-xs text-gray-400 mt-1">过程分：{q.process_score}分</div>
                    )}
                  </div>
                )}
              </div>
            ))}
            <Link href="/student/dashboard" className="btn-secondary w-full block text-center">返回主页</Link>
          </div>
        )}
      </main>
    </div>
  );
}

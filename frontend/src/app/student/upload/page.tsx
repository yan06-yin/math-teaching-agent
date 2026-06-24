"use client";
import { useState } from "react";
import Link from "next/link";
import axios from "axios";

export default function UploadPage() {
  const [file, setFile] = useState<File | null>(null);
  const [preview, setPreview] = useState<string | null>(null);
  const [manualInput, setManualInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<any>(null);
  const [statusMsg, setStatusMsg] = useState("");

  const handleSubmit = async () => {
    if (!file && !manualInput.trim()) return;
    setLoading(true); setResult(null); setStatusMsg("上传中...");
    try {
      const fd = new FormData();
      if (file) fd.append("file", file);
      if (manualInput.trim()) fd.append("student_answers", manualInput);
      const res = await axios.post(`/api/homework/upload`, fd, {
        headers: { Authorization: `Bearer ${localStorage.getItem("token")}` }, // 不设 Content-Type，让 axios 自动处理 boundary
      });
      const sid = res.data.submission_id;
      setStatusMsg("AI 正在批改中，请稍候...");

      // 轮询等待批改完成
      let attempts = 0;
      const maxAttempts = 60; // 最多等 3 分钟（3s 间隔）
      while (attempts < maxAttempts) {
        await new Promise(resolve => setTimeout(resolve, 3000));
        attempts++;
        const statusRes = await axios.get(`/api/homework/upload/${sid}/status`, {
          headers: { Authorization: `Bearer ${localStorage.getItem("token")}` },
        });
        if (statusRes.data.status === "done") {
          setResult(statusRes.data.result || statusRes.data);
          setStatusMsg("");
          setLoading(false);
          return;
        }
        if (statusRes.data.status === "error") {
          alert("批改失败：" + (statusRes.data.error || "未知错误"));
          setLoading(false);
          return;
        }
      }
      alert("批改超时，请稍后在作业列表中查看结果");
    } catch (e: any) { alert("上传失败：" + (e.response?.data?.detail || e.message)); }
    finally { setLoading(false); }
  };

  return (
    <div className="min-h-screen bg-gray-50">
      <nav className="bg-white border-b px-6 py-4"><div className="max-w-4xl mx-auto flex items-center justify-between"><Link href="/student/dashboard" className="text-[#6366f1] hover:underline text-sm">← 返回首页</Link><span className="font-semibold">拍照批改</span><div /></div></nav>
      <main className="max-w-4xl mx-auto px-6 py-8">
        {!result ? (
          <>
            <div className="card mb-6">
              <h3 className="font-semibold mb-4">上传作业照片</h3>
              <div className="border-2 border-dashed rounded-xl p-12 text-center border-gray-200">
                <div className="text-4xl mb-3">📷</div>
                <p className="text-gray-500 mb-2">支持 JPG、PNG 格式</p>
                <input type="file" accept="image/*" onChange={e => { const f = e.target.files?.[0]; if (f) { setFile(f); setPreview(URL.createObjectURL(f)); }}} className="block mx-auto" />
                {preview && <img src={preview} alt="preview" className="max-h-64 mx-auto mt-4 rounded-lg shadow" />}
              </div>
            </div>
            <div className="card mb-6">
              <h3 className="font-semibold mb-4">或手动输入题目和答案</h3>
              <textarea className="input min-h-[120px]" placeholder="1. 解方程 2x+3=7&#10;答案：x=2" value={manualInput} onChange={e => setManualInput(e.target.value)} />
            </div>
            <button onClick={handleSubmit} disabled={!file && !manualInput.trim() || loading} className="btn-primary w-full text-lg py-3">{loading ? (statusMsg || "AI 正在批改中...") : "🤖 开始批改"}</button>
          </>
        ) : (
          <div className="space-y-6">
            <div className="card"><h3 className="font-semibold text-lg mb-4">批改结果</h3><div className="text-4xl font-bold text-center text-[#6366f1] mb-4">{result.score}分</div>{result.total_count > 0 && <p className="text-center text-sm text-gray-500 mb-2">正确 {result.correct_count}/{result.total_count} 题</p>}{result.comments && <div className="p-4 bg-[#eef2ff] rounded-lg mb-4"><p className="text-indigo-800">{result.comments}</p></div>}</div>
            {result.wrong_questions?.filter((q: any) => !q.correct).map((q: any, i: number) => (
              <div key={i} className="card p-4 bg-red-50"><div className="font-medium mb-1">{q.question}</div>{q.student_answer && <div className="text-sm text-red-600">你的答案：{q.student_answer}</div>}{q.correct_answer && <div className="text-sm text-green-600">正确答案：{q.correct_answer}</div>}{q.explanation && <div className="text-sm text-gray-700 mt-2">💡 {q.explanation}</div>}</div>
            ))}
            <Link href="/student/dashboard" className="btn-secondary w-full block text-center">返回主页</Link>
          </div>
        )}
      </main>
    </div>
  );
}

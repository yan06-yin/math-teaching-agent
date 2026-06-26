"use client";
import { useState, useEffect, useRef } from "react";
import Link from "next/link";
import axios from "axios";

/** 将 SVG 字符串编码为 data URI，用 <img> 渲染，避免 dangerouslySetInnerHTML 导致的 XSS。
 *  浏览器对 <img src="data:image/svg+xml,..."> 内的脚本不执行，比直接 innerHTML 安全得多。 */
function svgToDataUri(svg: string): string {
  if (!svg) return "";
  // 移除明显危险内容（防御性，img 渲染本身已阻止脚本执行）
  const cleaned = svg
    .replace(/<script[\s\S]*?<\/script>/gi, "")
    .replace(/on\w+="[^"]*"/gi, "")
    .replace(/on\w+='[^']*'/gi, "")
    .replace(/javascript:/gi, "");
  // encodeURIComponent 处理特殊字符，避免 base64 编码开销
  return `data:image/svg+xml;utf8,${encodeURIComponent(cleaned)}`;
}

export default function ExamPage() {
  const [config, setConfig] = useState({ knowledgePoints: "", difficulty: 3, questionCount: 5, withImages: false });
  const [questions, setQuestions] = useState<any[]>([]);
  const [answers, setAnswers] = useState<string[]>([]);
  const [step, setStep] = useState<"config" | "taking" | "grading">("config");
  const [loading, setLoading] = useState(false);
  const [examId, setExamId] = useState<number | null>(null);
  const [result, setResult] = useState<any>(null);
  const [errorMsg, setErrorMsg] = useState("");
  const [pollStatus, setPollStatus] = useState("");
  const [pastExams, setPastExams] = useState<any[]>([]);

  const [imageFailed, setImageFailed] = useState<Record<number, boolean>>({});

  const handleImageError = (idx: number) => {
    setImageFailed(f => ({ ...f, [idx]: true }));
  };

  const token = typeof window !== "undefined" ? localStorage.getItem("token") : "";
  const headers = { Authorization: `Bearer ${token}` };
  // 标记组件是否仍挂载，避免轮询中在已卸载组件上 setState
  const isMountedRef = useRef(true);

  // 加载时拉取历史考试记录 & 检查 URL 参数
  useEffect(() => {
    if (!token) { window.location.href = "/"; return; }
    isMountedRef.current = true;
    axios.get("/api/exam/my", { headers }).then(r => { if (isMountedRef.current) setPastExams(r.data); }).catch(() => {});
    return () => { isMountedRef.current = false; };
  }, []);

  const pollWithTimeout = async (url: string, maxSec = 300, intervalMs = 3000) => {
    const maxAttempts = Math.floor((maxSec * 1000) / intervalMs);
    for (let i = 0; i < maxAttempts; i++) {
      await new Promise(r => setTimeout(r, intervalMs));
      if (!isMountedRef.current) throw new Error("component unmounted");
      const elapsed = Math.round((i * intervalMs) / 1000);
      if (elapsed < 60) setPollStatus(`⏳ 正在出题... ${elapsed}s`);
      else if (elapsed < 120) setPollStatus(`⏳ AI 运算中，请稍候... ${elapsed}s`);
      else setPollStatus(`⏳ 还在生成... ${elapsed}s（AI 运算越久题目质量越高）`);
      const res = await axios.get(url, { headers, timeout: 10000 });
      if (!isMountedRef.current) throw new Error("component unmounted");
      if (res.data.status === "done") return res.data;
      if (res.data.status === "error") throw new Error(res.data.error || "处理失败");
    }
    throw new Error("处理超时（5 分钟），请刷新后重试");
  };

  const handleGenerate = async () => {
    setLoading(true);
    setErrorMsg("");
    setPollStatus("");
    try {
      const res = await axios.post(`/api/exam/generate`, {
        knowledge_points: config.knowledgePoints ? config.knowledgePoints.split(/[,，]/).map(s => s.trim()) : [],
        difficulty: config.difficulty, question_count: config.questionCount, with_images: config.withImages,
      }, { headers, timeout: 30000 });
      const eid = res.data.exam_id;
      setExamId(eid);

      const data = await pollWithTimeout(`/api/exam/generate/${eid}/status`);
      const qs = data.questions || [];
      setQuestions(qs);
      setAnswers(new Array(qs.length).fill(""));
      setImageFailed({}); // 新试卷清空图片失败标记
      setStep("taking");
    } catch (e: any) {
      setErrorMsg(e.response?.data?.detail || e.message || "出题失败");
    } finally {
      setLoading(false);
      setPollStatus("");
    }
  };

  const handleSubmit = async () => {
    setLoading(true);
    setErrorMsg("");
    setPollStatus("");
    try {
      await axios.post(`/api/exam/${examId}/submit`, {
        answers: answers.map((a, i) => ({ question_index: i, answer: a })),
      }, { headers, timeout: 30000 });

      const data = await pollWithTimeout(`/api/exam/${examId}/status`, 300);
      setResult(data);
      setImageFailed({}); // 切换到结果页清空图片失败标记
      setStep("grading");
      // 刷新历史记录
      axios.get("/api/exam/my", { headers }).then(r => setPastExams(r.data)).catch(() => {});
    } catch (e: any) {
      setErrorMsg(e.response?.data?.detail || e.message || "提交失败");
    } finally {
      setLoading(false);
      setPollStatus("");
    }
  };

  const viewPastExam = async (id: number) => {
    setLoading(true);
    setErrorMsg("");
    try {
      const res = await axios.get(`/api/exam/${id}/report`, { headers, timeout: 10000 });
      setExamId(id);
      setResult(res.data);
      setImageFailed({}); // 查看历史考试时清空图片失败标记
      setStep("grading");
    } catch (e: any) {
      setErrorMsg(e.response?.data?.detail || e.message || "加载失败");
    } finally {
      setLoading(false);
    }
  };

  // 是否显示"正在出题/批改"的独立状态页
  if (loading && (pollStatus || step !== "grading") && !result) {
    const currentStep = step === "config" ? 1 : step === "taking" ? 3 : 4;
    const elapsed = pollStatus ? parseInt(pollStatus.match(/(\d+)s/)?.[1] || "0") : 0;
    const progressPct = Math.min(95, elapsed * 2); // 每秒约2%，最大95%

    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center">
        <div className="text-center max-w-md mx-auto px-6">
          {/* 步骤指示器 */}
          <div className="flex items-center justify-center gap-2 mb-6">
            {["配置", "出题", "答题", "批改", "结果"].map((s, i) => (
              <div key={i} className="flex items-center gap-1">
                <div className={`w-7 h-7 rounded-full flex items-center justify-center text-xs font-semibold ${
                  i + 1 < currentStep ? "bg-green-500 text-white" :
                  i + 1 === currentStep ? "bg-indigo-500 text-white animate-pulse" :
                  "bg-gray-200 text-gray-400"
                }`}>{i + 1 < currentStep ? "✓" : i + 1}</div>
                {i < 4 && <div className={`w-6 h-0.5 ${i + 1 < currentStep ? "bg-green-500" : "bg-gray-200"}`} />}
              </div>
            ))}
          </div>
          {/* 进度条 */}
          <div className="w-full bg-gray-200 rounded-full h-2 mb-4">
            <div className="bg-indigo-500 h-2 rounded-full transition-all duration-1000" style={{ width: `${progressPct}%` }} />
          </div>
          <div className="spinner spinner-lg mb-4 mx-auto"></div>
          <p className="text-gray-600 font-medium">{pollStatus || "处理中..."}</p>
          <p className="text-gray-400 text-sm mt-2">请勿关闭页面</p>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gray-50">
      <nav className="bg-white border-b px-6 py-4"><div className="max-w-4xl mx-auto flex items-center justify-between"><Link href="/student/dashboard" className="text-[#6366f1] hover:underline text-sm">← 返回首页</Link><span className="font-semibold">{step === "config" ? "智能出题" : step === "taking" ? "答题中" : "批改结果"}</span><div /></div></nav>
      <main className="max-w-4xl mx-auto px-6 py-8">
        {step === "config" && (
          <>
            <div className="card max-w-lg mx-auto">
              <h3 className="font-semibold mb-6">出题设置</h3>
              <div className="space-y-4">
                <div><label className="block text-sm font-medium mb-1">薄弱知识点</label><input className="input" placeholder="一元二次方程,相似三角形" value={config.knowledgePoints} onChange={e => setConfig({...config, knowledgePoints: e.target.value})} /></div>
                <div><label className="block text-sm font-medium mb-1">难度：{config.difficulty}/5</label><input type="range" min="1" max="5" value={config.difficulty} onChange={e => setConfig({...config, difficulty: +e.target.value})} className="w-full" /></div>
                <div><label className="block text-sm font-medium mb-1">题目：{config.questionCount}</label><input type="range" min="1" max="30" value={config.questionCount} onChange={e => setConfig({...config, questionCount: +e.target.value})} className="w-full" /></div>
                <label className="flex items-center gap-2 text-sm py-1"><input type="checkbox" checked={config.withImages} onChange={e => setConfig({...config, withImages: e.target.checked})} className="rounded" /> 🎨 高清配图（立体几何/实景图用，每题多等 5-10 秒）</label>
                <button onClick={handleGenerate} disabled={loading} className="btn-primary w-full py-3">{loading ? `⏳ ${pollStatus || "出题中..."}` : "🚀 生成试卷"}</button>
              </div>
              {errorMsg && (
                <div className="p-3 bg-red-50 text-red-600 text-sm rounded-lg border border-red-100 mt-4">
                  <p>⚠️ {errorMsg}</p>
                  <button onClick={handleGenerate} className="mt-2 text-xs text-indigo-600 hover:underline">🔄 重新出题</button>
                </div>
              )}
            </div>

            {/* 历史考试记录 */}
            {pastExams.length > 0 && (
              <div className="card mt-6">
                <h3 className="font-semibold mb-3">📋 历史考试记录</h3>
                <div className="space-y-2">
                  {pastExams.map((e, idx) => (
                    <button key={e.id} onClick={() => viewPastExam(e.id)} className="w-full text-left p-3 rounded-lg border hover:bg-gray-50 transition flex items-center justify-between cursor-pointer">
                      <div><span className="font-medium">第{pastExams.length - idx}次考试</span><span className="text-sm text-gray-400 ml-2">{e.questions_count} 题</span></div>
                      <div className="flex items-center gap-2"><span className="text-lg font-bold text-[#6366f1]">{e.score ?? "—"}</span><span className="text-gray-400 text-sm">分 →</span></div>
                    </button>
                  ))}
                </div>
              </div>
            )}
          </>
        )}
        {step === "taking" && (
          <div className="space-y-6">
            {questions.map((q, i) => (
              <div key={i} className="card">
                <div className="flex items-start gap-3">
                  <span className="w-8 h-8 bg-[#eef2ff] text-[#6366f1] rounded-full flex items-center justify-center text-sm font-medium flex-shrink-0">{i+1}</span>
                  <div className="flex-1">
                    <p className="text-gray-900 mb-1">{q.question}</p>
                    {q.image_url && !imageFailed[i] ? (
                      <img src={q.image_url} alt="题目示意图" className="max-w-full max-h-60 rounded-lg mx-auto my-2 border" onError={() => handleImageError(i)} />
                    ) : q.image_svg ? (
                      <img src={svgToDataUri(q.image_svg)} alt="题目示意图" className="max-w-full max-h-60 rounded-lg mx-auto my-2 border" />
                    ) : null}
                    <span className="text-xs text-gray-400">{q.knowledge_point}</span>
                    <textarea className="input mt-3 min-h-[80px]" placeholder="输入答案..." value={answers[i] || ""} onChange={e => { const a=[...answers]; a[i]=e.target.value; setAnswers(a); }} />
                  </div>
                </div>
              </div>
            ))}
            <button onClick={handleSubmit} disabled={loading} className="btn-primary w-full py-3">{loading ? `⏳ ${pollStatus || "AI 批改中..."}` : "✅ 提交答卷"}</button>
          {errorMsg && (
            <div className="p-3 bg-red-50 text-red-600 text-sm rounded-lg border border-red-100 mt-4">
              <p>⚠️ {errorMsg}</p>
              <button onClick={handleSubmit} className="mt-2 text-xs text-indigo-600 hover:underline">🔄 重新提交</button>
            </div>
          )}
          </div>
        )}
        {step === "grading" && result && (
          <div className="space-y-6">
            <div className="card text-center"><div className="text-6xl font-bold text-[#6366f1] my-4">{result.score ?? "—"}</div><p className="text-gray-500 text-sm">{new Date(result.created_at).toLocaleDateString("zh-CN")}</p></div>
            {result.questions?.map((q: any, i: number) => {
              const detail = result.details?.[i];
              const isCorrect = detail ? detail.correct : false;
              return (
              <div key={i} className={`card border-l-4 ${isCorrect ? 'border-l-green-500' : 'border-l-red-400'}`}>
                <div className="flex items-start gap-3">
                  <span className="text-xl">{isCorrect ? "✅" : "❌"}</span>
                  <div className="flex-1">
                    <p className="text-gray-900 mb-2">{q.question}</p>
                    {q.image_url && !imageFailed[i] ? (
                      <img src={q.image_url} alt="示意图" className="max-w-full max-h-60 rounded-lg mx-auto my-2 border" onError={() => handleImageError(i)} />
                    ) : q.image_svg ? (
                      <img src={svgToDataUri(q.image_svg)} alt="示意图" className="max-w-full max-h-60 rounded-lg mx-auto my-2 border" />
                    ) : null}
                    <div className="grid grid-cols-2 gap-4 text-sm">
                      <div><span className="text-gray-500">你的答案：</span><span>{result.student_answers?.[i]?.answer || "未作答"}</span></div>
                      <div><span className="text-gray-500">正确答案：</span><span className="text-green-600">{q.answer}</span></div>
                    </div>
                    {q.explanation && <div className="mt-2 p-3 bg-blue-50 text-blue-800 text-sm rounded-lg">💡 {q.explanation}</div>}
                  </div>
                </div>
              </div>
              );
            })}
            <div className="flex gap-3"><Link href="/student/report" className="btn-primary flex-1 text-center py-3">📊 查看诊断报告</Link><Link href="/student/dashboard" className="btn-secondary flex-1 text-center py-3">返回主页</Link></div>
          </div>
        )}
      </main>
    </div>
  );
}

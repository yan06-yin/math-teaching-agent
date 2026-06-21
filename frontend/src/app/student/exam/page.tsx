"use client";
import { useState } from "react";
import Link from "next/link";
import axios from "axios";

export default function ExamPage() {
  const [config, setConfig] = useState({ knowledgePoints: "", difficulty: 3, questionCount: 5 });
  const [questions, setQuestions] = useState<any[]>([]);
  const [answers, setAnswers] = useState<string[]>([]);
  const [step, setStep] = useState<"config" | "taking" | "grading">("config");
  const [loading, setLoading] = useState(false);
  const [examId, setExamId] = useState<number | null>(null);
  const [result, setResult] = useState<any>(null);

  const token = typeof window !== "undefined" ? localStorage.getItem("token") : "";
  const headers = { Authorization: `Bearer ${token}` };

  const handleGenerate = async () => {
    setLoading(true);
    try {
      // 1. 触发后台出题（立即返回 task_id + exam_id）
      const res = await axios.post(`/api/exam/generate`, {
        knowledge_points: config.knowledgePoints ? config.knowledgePoints.split(/[,，]/).map(s => s.trim()) : [],
        difficulty: config.difficulty, question_count: config.questionCount,
      }, { headers, timeout: 30000 });
      const eid = res.data.exam_id;
      setExamId(eid);

      // 2. 轮询等待试卷生成完成
      let attempts = 0;
      const maxAttempts = 60; // 最多等 3 分钟（3s 间隔）
      while (attempts < maxAttempts) {
        await new Promise(resolve => setTimeout(resolve, 3000));
        attempts++;
        const statusRes = await axios.get(`/api/exam/generate/${eid}/status`, { headers, timeout: 10000 });
        if (statusRes.data.status === "done") {
          const qs = statusRes.data.questions || [];
          setQuestions(qs);
          setAnswers(new Array(qs.length).fill(""));
          setStep("taking");
          setLoading(false);
          return;
        }
        if (statusRes.data.status === "error") {
          alert("出题失败：" + (statusRes.data.error || "未知错误"));
          setLoading(false);
          return;
        }
        // 每 15 秒更新一下状态提示
        if (attempts % 5 === 0) {
          setLoading(true); // 保持 loading
        }
      }
      alert("出题超时，请稍后重试");
    } catch (e: any) { alert("出题失败：" + (e.response?.data?.detail || e.message)); } finally { setLoading(false); }
  };

  const handleSubmit = async () => {
    setLoading(true);
    try {
      // 提交答卷（立即返回）
      await axios.post(`/api/exam/${examId}/submit`, {
        answers: answers.map((a, i) => ({ question_index: i, answer: a })),
      }, { headers, timeout: 30000 });

      // 轮询等待批改完成
      let attempts = 0;
      const maxAttempts = 60; // 最多等 3 分钟（3s 间隔）
      while (attempts < maxAttempts) {
        await new Promise(resolve => setTimeout(resolve, 3000));
        attempts++;
        const statusRes = await axios.get(`/api/exam/${examId}/status`, { headers, timeout: 10000 });
        if (statusRes.data.status === "done") {
          setResult(statusRes.data);
          setStep("grading");
          setLoading(false);
          return;
        }
        if (statusRes.data.status === "error") {
          alert("批改失败：" + (statusRes.data.error || "未知错误"));
          setLoading(false);
          return;
        }
      }
      alert("批改超时，请稍后在诊断报告页面查看结果");
      setStep("grading");
    } catch (e: any) { alert("提交失败：" + (e.response?.data?.detail || e.message)); } finally { setLoading(false); }
  };

  return (
    <div className="min-h-screen bg-gray-50">
      <nav className="bg-white border-b px-6 py-4"><div className="max-w-4xl mx-auto flex items-center justify-between"><Link href="/student/dashboard" className="text-[#6366f1] hover:underline text-sm">← 返回首页</Link><span className="font-semibold">{step === "config" ? "智能出题" : step === "taking" ? "答题中" : "批改结果"}</span><div /></div></nav>
      <main className="max-w-4xl mx-auto px-6 py-8">
        {step === "config" && (
          <div className="card max-w-lg mx-auto">
            <h3 className="font-semibold mb-6">出题设置</h3>
            <div className="space-y-4">
              <div><label className="block text-sm font-medium mb-1">薄弱知识点</label><input className="input" placeholder="一元二次方程,相似三角形" value={config.knowledgePoints} onChange={e => setConfig({...config, knowledgePoints: e.target.value})} /></div>
              <div><label className="block text-sm font-medium mb-1">难度：{config.difficulty}/5</label><input type="range" min="1" max="5" value={config.difficulty} onChange={e => setConfig({...config, difficulty: +e.target.value})} className="w-full" /></div>
              <div><label className="block text-sm font-medium mb-1">题目：{config.questionCount}</label><input type="range" min="1" max="30" value={config.questionCount} onChange={e => setConfig({...config, questionCount: +e.target.value})} className="w-full" /></div>
              <button onClick={handleGenerate} disabled={loading} className="btn-primary w-full py-3">{loading ? "出题中..." : "🚀 生成试卷"}</button>
            </div>
          </div>
        )}
        {step === "taking" && (
          <div className="space-y-6">
            {questions.map((q, i) => (
              <div key={i} className="card">
                <div className="flex items-start gap-3">
                  <span className="w-8 h-8 bg-[#eef2ff] text-[#6366f1] rounded-full flex items-center justify-center text-sm font-medium flex-shrink-0">{i+1}</span>
                  <div className="flex-1">
                    <p className="text-gray-900 mb-1">{q.question}</p>
                    {q.image_url && <img src={q.image_url} alt="题目示意图" className="max-w-full max-h-60 rounded-lg mx-auto my-2 border" />}
                    <span className="text-xs text-gray-400">{q.knowledge_point}</span>
                    <textarea className="input mt-3 min-h-[80px]" placeholder="输入答案..." value={answers[i] || ""} onChange={e => { const a=[...answers]; a[i]=e.target.value; setAnswers(a); }} />
                  </div>
                </div>
              </div>
            ))}
            <button onClick={handleSubmit} disabled={loading} className="btn-primary w-full py-3">{loading ? "🤖 AI 批改中，请耐心等待..." : "✅ 提交答卷"}</button>
          </div>
        )}
        {step === "grading" && result && (
          <div className="space-y-6">
            <div className="card text-center"><div className="text-6xl font-bold text-[#6366f1] my-4">{result.score ?? "—"}</div></div>
            {result.questions?.map((q: any, i: number) => {
              const detail = result.details?.[i];
              const isCorrect = detail ? detail.correct : false;
              return (
              <div key={i} className={`card border-l-4 ${isCorrect ? 'border-l-green-500' : 'border-l-red-400'}`}>
                <div className="flex items-start gap-3">
                  <span className="text-xl">{isCorrect ? "✅" : "❌"}</span>
                  <div className="flex-1">
                    <p className="text-gray-900 mb-2">{q.question}</p>
                    {q.image_url && <img src={q.image_url} alt="示意图" className="max-w-full max-h-60 rounded-lg mx-auto my-2 border" />}
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

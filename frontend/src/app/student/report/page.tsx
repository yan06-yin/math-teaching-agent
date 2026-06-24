"use client";
import { useState, useEffect } from "react";
import Link from "next/link";
import axios from "axios";

export default function ReportPage() {
  const [exams, setExams] = useState<any[]>([]);
  const [selected, setSelected] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [imageFailed, setImageFailed] = useState<Record<string, boolean>>({});

  useEffect(() => {
    const token = localStorage.getItem("token");
    if (!token) return;
    axios.get("/api/exam/my", { headers: { Authorization: `Bearer ${token}` } }).then(r => {
      setExams(r.data);
      if (r.data.length > 0) loadDetail(r.data[0].id);
    }).catch(() => {}).finally(() => setLoading(false));
  }, []);

  const loadDetail = async (id: number) => {
    const res = await axios.get(`/api/exam/${id}/report`, { headers: { Authorization: `Bearer ${localStorage.getItem("token")}` } });
    setSelected(res.data);
  };

  const handleImageError = (key: string) => {
    setImageFailed(f => ({ ...f, [key]: true }));
  };

  if (loading) return <div className="min-h-screen flex items-center justify-center"><div className="spinner"></div></div>;

  return (
    <div className="min-h-screen bg-gray-50">
      <nav className="bg-white border-b px-6 py-4"><div className="max-w-4xl mx-auto flex items-center justify-between"><Link href="/student/dashboard" className="text-[#6366f1] hover:underline text-sm">← 返回首页</Link><span className="font-semibold">诊断报告</span><div /></div></nav>
      <main className="max-w-4xl mx-auto px-6 py-8">
        <div className="card mb-6">
          <h3 className="font-semibold mb-3">考试历史</h3>
          <div className="flex gap-2 overflow-x-auto pb-2">
            {exams.map((e) => (
              <button key={e.id} onClick={() => loadDetail(e.id)} className={`flex-shrink-0 px-4 py-2 rounded-lg text-sm font-medium transition cursor-pointer ${selected?.id === e.id ? "bg-[#4f46e5] text-white" : "bg-gray-100 text-gray-600 hover:bg-gray-200"}`}>第{e.id}次 · {e.score ?? "?"}分</button>
            ))}
            {exams.length === 0 && <span className="text-gray-400 text-sm">暂无考试记录</span>}
          </div>
        </div>
        {selected && (
          <>
            {/* 分数概览 */}
            <div className="card text-center mb-6">
              <div className="text-6xl font-bold text-[#6366f1] my-4">{selected.score ?? "—"}</div>
              <p className="text-gray-500">{new Date(selected.created_at).toLocaleDateString("zh-CN")}</p>
            </div>

            {/* 逐题批改详情 */}
            {selected.questions?.length > 0 && (
              <div className="space-y-4 mb-6">
                <h3 className="text-lg font-semibold">📝 逐题详情</h3>
                {selected.questions.map((q: any, i: number) => {
                  const detail = selected.details?.[i];
                  const isCorrect = detail ? detail.correct : false;
                  const stuAns = selected.student_answers?.[i]?.answer || "未作答";
                  const imgKey = `q-${selected.id}-${i}`;
                  return (
                    <div key={i} className={`card border-l-4 ${isCorrect ? 'border-l-green-500' : 'border-l-red-400'}`}>
                      <div className="flex items-start gap-3">
                        <span className="text-xl">{isCorrect ? "✅" : "❌"}</span>
                        <div className="flex-1 min-w-0">
                          <p className="text-gray-900 mb-2 font-medium">{q.question}</p>
                          {q.image_url && !imageFailed[imgKey] ? (
                            <img src={q.image_url} alt="示意图" className="max-w-full max-h-60 rounded-lg mx-auto my-2 border" onError={() => handleImageError(imgKey)} />
                          ) : q.image_svg ? (
                            <div className="flex justify-center my-2" dangerouslySetInnerHTML={{ __html: q.image_svg }} />
                          ) : null}
                          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 text-sm mt-2">
                            <div className="p-2 bg-gray-50 rounded"><span className="text-gray-500 block mb-1">你的答案</span><span className={isCorrect ? "" : "text-red-600"}>{stuAns}</span></div>
                            <div className="p-2 bg-gray-50 rounded"><span className="text-gray-500 block mb-1">正确答案</span><span className="text-green-600">{q.answer}</span></div>
                          </div>
                          {detail && !isCorrect && detail.feedback && (
                            <div className="mt-2 p-3 bg-red-50 text-red-700 text-sm rounded-lg">{detail.feedback}</div>
                          )}
                          {q.explanation && (
                            <div className="mt-2 p-3 bg-blue-50 text-blue-800 text-sm rounded-lg">💡 {q.explanation}</div>
                          )}
                          <span className="inline-block mt-2 text-xs text-gray-400 bg-gray-100 px-2 py-0.5 rounded">{q.knowledge_point}</span>
                        </div>
                      </div>
                    </div>
                  );
                })}
              </div>
            )}

            {/* AI 诊断分析 */}
            {selected.diagnostic_report && (
              <div className="card mb-6"><h3 className="font-semibold mb-4">AI 诊断分析</h3><pre className="bg-gray-50 p-4 rounded-lg text-sm whitespace-pre-wrap text-gray-700">{typeof selected.diagnostic_report === "string" ? selected.diagnostic_report : JSON.stringify(selected.diagnostic_report, null, 2)}</pre></div>
            )}

            {/* 学习计划 */}
            {selected.learning_plan?.length > 0 && (
              <div className="card"><h3 className="font-semibold mb-4">📅 学习计划</h3>
                <div className="space-y-3">{selected.learning_plan.map((item: any, i: number) => (
                  <div key={i} className="flex items-start gap-3 p-3 bg-[#eef2ff] rounded-lg">
                    <span className="flex-shrink-0 w-8 h-8 bg-[#6366f1] text-white rounded-full flex items-center justify-center text-sm font-medium">{i+1}</span>
                    <div><div className="font-medium">{item.topic || item.day}</div><div className="text-sm text-gray-500">{item.focus}</div></div>
                  </div>
                ))}</div>
              </div>
            )}
          </>
        )}
      </main>
    </div>
  );
}

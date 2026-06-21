"use client";
import { useState } from "react";
import { useRouter } from "next/navigation";
import axios from "axios";

const API_BASE = typeof window !== "undefined" ? (localStorage.getItem("apiBase") || "/api") : "/api";

export default function LoginPage() {
  const router = useRouter();
  const [userType, setUserType] = useState<"student" | "teacher" | "admin">("student");
  const [mode, setMode] = useState<"login" | "register">("login");
  const [name, setName] = useState("");
  const [studentId, setStudentId] = useState("");
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [level, setLevel] = useState("初中");
  const [school, setSchool] = useState("");
  const [inviteCode, setInviteCode] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const api = (url: string) => `/api${url}`;

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    if (password !== confirmPassword && mode === "register") {
      setError("两次输入的密码不一致");
      return;
    }
    if (password.length < 6) {
      setError("密码至少6位");
      return;
    }
    setLoading(true);
    try {
      if (userType === "admin") {
        const res = await axios.post(api("/auth/teacher/login"), { username, password }, { timeout: 10000 });
        localStorage.setItem("token", res.data.access_token);
        localStorage.setItem("userName", "管理员");
        localStorage.setItem("userType", "admin");
        router.push("/admin/dashboard");
      } else if (userType === "student") {
        const url = mode === "register" ? api("/auth/register") : api("/auth/login");
        const payload = mode === "register"
          ? { name, student_id: studentId, password, school_level: level, invite_code: inviteCode || undefined }
          : { student_id: studentId, name, password };
        const res = await axios.post(url, payload, { timeout: 10000 });
        localStorage.setItem("token", res.data.access_token);
        localStorage.setItem("studentId", String(res.data.student_id));
        localStorage.setItem("userName", name);
        localStorage.setItem("userType", "student");
        router.push("/student/dashboard");
      } else {
        const url = mode === "register" ? api("/auth/teacher/register") : api("/auth/teacher/login");
        const payload = mode === "register"
          ? { name, username, password, school }
          : { username, password };
        const res = await axios.post(url, payload, { timeout: 10000 });
        localStorage.setItem("token", res.data.access_token);
        localStorage.setItem("userName", name);
        localStorage.setItem("userType", "teacher");
        router.push("/teacher/dashboard");
      }
    } catch (err: any) {
      setError(err.response?.data?.detail || "操作失败，请重试");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen flex items-center justify-center bg-gradient-to-br from-indigo-50 via-white to-sky-50 p-4">
      <div className="w-full max-w-md">
        {/* Logo / Header */}
        <div className="text-center mb-8">
          <div className="inline-flex items-center justify-center w-18 h-18 bg-gradient-to-br from-indigo-500 to-purple-600 rounded-2xl mb-5 shadow-lg">
            <span className="text-4xl">📐</span>
          </div>
          <h1 className="text-3xl font-bold gradient-text">数学教学智能体</h1>
          <p className="text-gray-500 mt-2 text-sm">基于 AI 的智能数学辅导系统</p>
        </div>

        <div className="card border-0 shadow-lg rounded-2xl">
          {/* 角色切换 */}
          <div className="flex gap-1.5 mb-5 p-1 bg-gray-100 rounded-xl">
            {[
              { key: "student" as const, label: "🎒 学生", icon: "🎒" },
              { key: "teacher" as const, label: "👨‍🏫 教师", icon: "👨‍🏫" },
              { key: "admin" as const, label: "⚙️ 管理", icon: "⚙️" },
            ].map(item => (
              <button key={item.key}
                className={`flex-1 py-2.5 rounded-lg text-sm font-medium transition-all ${userType === item.key ? "bg-white shadow-sm text-gray-900 font-semibold" : "text-gray-500 hover:text-gray-700"}`}
                onClick={() => { setUserType(item.key); setMode("login"); setError(""); }}>
                {item.label}
              </button>
            ))}
          </div>

          {/* 登录/注册切换（管理只有登录） */}
          {userType !== "admin" && (
            <div className="flex gap-1.5 mb-6 p-1 bg-gray-100 rounded-xl">
              <button className={`flex-1 py-2 rounded-lg text-sm font-medium transition-all ${mode === "login" ? "bg-white shadow-sm text-gray-900" : "text-gray-500 hover:text-gray-700"}`}
                onClick={() => { setMode("login"); setError(""); }}>🔑 登录</button>
              <button className={`flex-1 py-2 rounded-lg text-sm font-medium transition-all ${mode === "register" ? "bg-white shadow-sm text-gray-900" : "text-gray-500 hover:text-gray-700"}`}
                onClick={() => { setMode("register"); setError(""); }}>📝 注册</button>
            </div>
          )}

          <form onSubmit={handleSubmit} className="space-y-4">
            {/* 管理员 */}
            {userType === "admin" ? (
              <>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1.5">管理员账号</label>
                  <input type="text" className="input" placeholder="admin" value={username} onChange={e => setUsername(e.target.value)} required />
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1.5">密码</label>
                  <input type="password" className="input" placeholder="请输入管理员密码" value={password} onChange={e => setPassword(e.target.value)} required />
                </div>
              </>
            ) : userType === "student" ? (
              <>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1.5">姓名</label>
                  <input type="text" className="input" placeholder="请输入姓名" value={name} onChange={e => setName(e.target.value)} required />
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1.5">学号</label>
                  <input type="text" className="input" placeholder="请输入学号" value={studentId} onChange={e => setStudentId(e.target.value)} required />
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1.5">密码</label>
                  <input type="password" className="input" placeholder="请输入密码" value={password} onChange={e => setPassword(e.target.value)} required />
                </div>
                {mode === "register" && (
                  <>
                    <div>
                      <label className="block text-sm font-medium text-gray-700 mb-1.5">确认密码</label>
                      <input type="password" className="input" placeholder="再次输入密码" value={confirmPassword} onChange={e => setConfirmPassword(e.target.value)} required />
                    </div>
                    <div>
                      <label className="block text-sm font-medium text-gray-700 mb-1.5">学段</label>
                      <select className="input" value={level} onChange={e => setLevel(e.target.value)}>
                        <option value="小学">🏫 小学</option><option value="初中">🏫 初中</option><option value="高中">🏫 高中</option>
                      </select>
                    </div>
                    <div>
                      <label className="block text-sm font-medium text-gray-700 mb-1.5">邀请码 <span className="text-gray-400 font-normal">（有班级邀请码可填）</span></label>
                      <input type="text" className="input" placeholder="选填" value={inviteCode} onChange={e => setInviteCode(e.target.value)} />
                    </div>
                  </>
                )}
              </>
            ) : (
              <>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1.5">姓名</label>
                  <input type="text" className="input" placeholder="请输入姓名" value={name} onChange={e => setName(e.target.value)} required />
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1.5">用户名</label>
                  <input type="text" className="input" placeholder="请输入用户名" value={username} onChange={e => setUsername(e.target.value)} required />
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1.5">密码</label>
                  <input type="password" className="input" placeholder="请输入密码" value={password} onChange={e => setPassword(e.target.value)} required />
                </div>
                {mode === "register" && (
                  <>
                    <div>
                      <label className="block text-sm font-medium text-gray-700 mb-1.5">确认密码</label>
                      <input type="password" className="input" placeholder="再次输入密码" value={confirmPassword} onChange={e => setConfirmPassword(e.target.value)} required />
                    </div>
                    <div>
                      <label className="block text-sm font-medium text-gray-700 mb-1.5">学校</label>
                      <input type="text" className="input" placeholder="请输入学校名称" value={school} onChange={e => setSchool(e.target.value)} />
                    </div>
                  </>
                )}
              </>
            )}

            {error && (
              <div className="p-3 bg-red-50 text-red-600 text-sm rounded-lg border border-red-100 flex items-center gap-2">
                <span>⚠️</span><span>{error}</span>
              </div>
            )}

            <button type="submit" disabled={loading}
              className="btn-primary w-full py-3 text-base">
              {loading ? (
                <span className="flex items-center gap-2"><span className="spinner !border-white !border-t-transparent !w-4 !h-4" /> 处理中...</span>
              ) : (
                mode === "login" || userType === "admin" ? "🚀 进入系统" : "📝 立即注册"
              )}
            </button>
          </form>
        </div>

        <p className="text-center text-xs text-gray-400 mt-6">
          数学教学智能体 v2.0 · 基于 AI 技术
        </p>
      </div>
    </div>
  );
}

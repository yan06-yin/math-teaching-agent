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
        // 管理员登录
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
    <div className="min-h-screen flex items-center justify-center bg-gradient-to-br from-indigo-50 via-white to-blue-50">
      <div className="card w-full max-w-md mx-4">
        <div className="text-center mb-6">
          <div className="inline-flex items-center justify-center w-16 h-16 bg-[#eef2ff] rounded-full mb-4">
            <span className="text-3xl">📐</span>
          </div>
          <h1 className="text-2xl font-bold text-gray-900">数学教学智能体</h1>
          <p className="text-gray-500 mt-2">基于 AI 的智能数学辅导系统</p>
        </div>
        <div className="flex gap-2 mb-4 p-1 bg-gray-100 rounded-lg">
          <button className={`flex-1 py-2 rounded-md text-sm font-medium transition ${userType === "student" ? "bg-white shadow text-gray-900" : "text-gray-500 hover:text-gray-700"}`} onClick={() => { setUserType("student"); setMode("login"); setError(""); }}>学生</button>
          <button className={`flex-1 py-2 rounded-md text-sm font-medium transition ${userType === "teacher" ? "bg-white shadow text-gray-900" : "text-gray-500 hover:text-gray-700"}`} onClick={() => { setUserType("teacher"); setMode("login"); setError(""); }}>教师</button>
          <button className={`flex-1 py-2 rounded-md text-sm font-medium transition ${userType === "admin" ? "bg-white shadow text-gray-900" : "text-gray-500 hover:text-gray-700"}`} onClick={() => { setUserType("admin"); setMode("login"); setError(""); }}>管理</button>
        </div>
        {userType !== "admin" && (
        <div className="flex gap-2 mb-6 p-1 bg-gray-100 rounded-lg">
          <button className={`flex-1 py-2 rounded-md text-sm font-medium transition ${mode === "login" ? "bg-white shadow text-gray-900" : "text-gray-500 hover:text-gray-700"}`} onClick={() => { setMode("login"); setError(""); }}>登录</button>
          <button className={`flex-1 py-2 rounded-md text-sm font-medium transition ${mode === "register" ? "bg-white shadow text-gray-900" : "text-gray-500 hover:text-gray-700"}`} onClick={() => { setMode("register"); setError(""); }}>注册</button>
        </div>
        )}
        <form onSubmit={handleSubmit} className="space-y-4">
          {userType === "admin" ? (
            <>
              <div><label className="block text-sm font-medium text-gray-700 mb-1">管理员用户名</label><input type="text" className="input" placeholder="admin" value={username} onChange={e => setUsername(e.target.value)} required /></div>
              <div><label className="block text-sm font-medium text-gray-700 mb-1">密码</label><input type="password" className="input" placeholder="请输入管理员密码" value={password} onChange={e => setPassword(e.target.value)} required /></div>
            </>
          ) : userType === "student" ? (
            <>
              <div><label className="block text-sm font-medium text-gray-700 mb-1">姓名</label><input type="text" className="input" placeholder="请输入姓名" value={name} onChange={e => setName(e.target.value)} required /></div>
              <div><label className="block text-sm font-medium text-gray-700 mb-1">学号</label><input type="text" className="input" placeholder="请输入学号" value={studentId} onChange={e => setStudentId(e.target.value)} required /></div>
              <div><label className="block text-sm font-medium text-gray-700 mb-1">密码</label><input type="password" className="input" placeholder="请输入密码" value={password} onChange={e => setPassword(e.target.value)} required /></div>
              {mode === "register" && (
                <>
                  <div><label className="block text-sm font-medium text-gray-700 mb-1">确认密码</label><input type="password" className="input" placeholder="再次输入密码" value={confirmPassword} onChange={e => setConfirmPassword(e.target.value)} required /></div>
                  <div><label className="block text-sm font-medium text-gray-700 mb-1">学段</label><select className="input" value={level} onChange={e => setLevel(e.target.value)}><option value="小学">小学</option><option value="初中">初中</option><option value="高中">高中</option></select></div>
                  <div><label className="block text-sm font-medium text-gray-700 mb-1">邀请码（可选）</label><input type="text" className="input" placeholder="有班级邀请码可填写" value={inviteCode} onChange={e => setInviteCode(e.target.value)} /></div>
                </>
              )}
            </>
          ) : (
            <>
              <div><label className="block text-sm font-medium text-gray-700 mb-1">姓名</label><input type="text" className="input" placeholder="请输入姓名" value={name} onChange={e => setName(e.target.value)} required /></div>
              <div><label className="block text-sm font-medium text-gray-700 mb-1">用户名</label><input type="text" className="input" placeholder="请输入用户名" value={username} onChange={e => setUsername(e.target.value)} required /></div>
              <div><label className="block text-sm font-medium text-gray-700 mb-1">密码</label><input type="password" className="input" placeholder="请输入密码" value={password} onChange={e => setPassword(e.target.value)} required /></div>
              {mode === "register" && (
                <>
                  <div><label className="block text-sm font-medium text-gray-700 mb-1">确认密码</label><input type="password" className="input" placeholder="再次输入密码" value={confirmPassword} onChange={e => setConfirmPassword(e.target.value)} required /></div>
                  <div><label className="block text-sm font-medium text-gray-700 mb-1">学校</label><input type="text" className="input" placeholder="请输入学校名称" value={school} onChange={e => setSchool(e.target.value)} /></div>
                </>
              )}
            </>
          )}
          {error && <div className="p-3 bg-red-50 text-red-600 text-sm rounded-lg">{error}</div>}
          <button type="submit" disabled={loading} className="btn-primary w-full">{loading ? "处理中..." : mode === "login" ? "登录" : "注册"}</button>
        </form>
      </div>
    </div>
  );
}

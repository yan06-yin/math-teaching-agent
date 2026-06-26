import axios, { AxiosError } from "axios";

export const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || "";

export function getToken(): string | null {
  if (typeof window === "undefined") return null;
  return localStorage.getItem("token");
}

export function getUserType(): string | null {
  if (typeof window === "undefined") return null;
  return localStorage.getItem("userType");
}

export function clearAuth() {
  if (typeof window === "undefined") return;
  localStorage.removeItem("token");
  localStorage.removeItem("userType");
  localStorage.removeItem("studentId");
  localStorage.removeItem("userName");
}

/** 向后兼容：旧代码用 headers() 手动注入 */
export function apiHeaders(): Record<string, string> {
  const t = getToken();
  return t ? { Authorization: `Bearer ${t}` } : {};
}

/** 统一 axios 实例：自动注入 baseURL、token，401 时清理并跳转登录 */
const api = axios.create({
  baseURL: API_BASE_URL,
  timeout: 60000,
});

api.interceptors.request.use((config) => {
  const t = getToken();
  if (t) {
    config.headers = config.headers || {};
    config.headers.Authorization = `Bearer ${t}`;
  }
  return config;
});

api.interceptors.response.use(
  (resp) => resp,
  (error: AxiosError) => {
    // 401：token 过期或无效，清理并跳转登录页（避免页面陷入"数据全空"死状态）
    if (error.response?.status === 401 && typeof window !== "undefined") {
      clearAuth();
      // 仅当不在登录页时跳转，避免循环
      if (!window.location.pathname.startsWith("/")) {
        window.location.href = "/";
      } else if (window.location.pathname !== "/") {
        window.location.href = "/";
      }
    }
    return Promise.reject(error);
  }
);

export default api;

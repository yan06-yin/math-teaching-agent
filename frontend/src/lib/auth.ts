export const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || "";
export function getToken() { if (typeof window === "undefined") return null; return localStorage.getItem("token"); }
export function apiHeaders() { const t = getToken(); return t ? { Authorization: `Bearer ${t}` } : {}; }

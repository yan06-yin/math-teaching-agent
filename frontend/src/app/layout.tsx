import type { Metadata } from "next";
import { ToastProvider } from "./toast";
import "./globals.css";

export const metadata: Metadata = {
  title: "数学教学智能体",
  description: "基于 AI 的智能数学辅导系统",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="zh-CN">
      <body className="min-h-full flex flex-col bg-gray-50 text-gray-900">
        <ToastProvider>{children}</ToastProvider>
      </body>
    </html>
  );
}

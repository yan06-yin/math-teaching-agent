import type { Metadata } from "next";
import { ToastProvider } from "./toast";
import "./globals.css";

export const metadata: Metadata = {
  title: "AI 智能作业批改系统",
  description: "基于 AI 的多学科作业批改系统，支持数学、语文、英语",
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

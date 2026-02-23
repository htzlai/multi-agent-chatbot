"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useState, useEffect } from "react";
import { cn } from "@/lib/utils";

interface SystemStatus {
  selectedModel: string | null;
  selectedSourcesCount: number;
  totalVectors: number;
  totalChats: number;
}

export function TopNav() {
  const pathname = usePathname();
  const [systemStatus, setSystemStatus] = useState<SystemStatus>({
    selectedModel: null,
    selectedSourcesCount: 0,
    totalVectors: 0,
    totalChats: 0,
  });
  const [isLoading, setIsLoading] = useState(true);

  // 获取系统状态
  useEffect(() => {
    const fetchStatus = async () => {
      try {
        const [modelRes, sourcesRes, statsRes, chatsRes] = await Promise.all([
          fetch("/api/selected_model"),
          fetch("/api/selected_sources"),
          fetch("/api/test/vector-stats"),
          fetch("/api/chats"),
        ]);

        const modelData = modelRes.ok ? await modelRes.json() : { model: null };
        const sourcesData = sourcesRes.ok ? await sourcesRes.json() : { sources: [] };
        const statsData = statsRes.ok ? await statsRes.json() : { total_entities: 0 };
        const chatsData = chatsRes.ok ? await chatsRes.json() : { chats: [] };

        setSystemStatus({
          selectedModel: modelData.model,
          selectedSourcesCount: sourcesData.sources?.length || 0,
          totalVectors: statsData.total_entities || 0,
          totalChats: chatsData.chats?.length || 0,
        });
      } catch (error) {
        console.error("Failed to fetch system status:", error);
      } finally {
        setIsLoading(false);
      }
    };

    fetchStatus();
    // 每30秒刷新一次状态
    const interval = setInterval(fetchStatus, 30000);
    return () => clearInterval(interval);
  }, []);

  // 导航项配置
  const navItems = [
    {
      name: "对话",
      nameEn: "Chat",
      href: "/",
      icon: (
        <svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
          <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z" />
        </svg>
      ),
      description: "与AI进行对话",
    },
    {
      name: "知识库控制台",
      nameEn: "RAG Console",
      href: "/ragtest",
      icon: (
        <svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
          <path d="M2 3h6a4 4 0 0 1 4 4v14a3 3 0 0 0-3-3H2z" />
          <path d="M22 3h-6a4 4 0 0 0-4 4v14a3 3 0 0 1 3-3h7z" />
        </svg>
      ),
      description: "管理和测试知识库",
    },
  ];

  const isActive = (href: string) => {
    if (href === "/") return pathname === "/";
    return pathname.startsWith(href);
  };

  return (
    <>
      {/* 顶部导航栏 */}
      <nav className="fixed top-0 left-0 right-0 z-50 h-16 border-b border-border/50 bg-background/80 backdrop-blur-xl">
        <div className="flex h-full items-center justify-between px-4 lg:px-8">
          
          {/* 左侧：品牌Logo */}
          <div className="flex items-center gap-3">
            <Link href="/" className="flex items-center gap-2.5 group">
              <div className="relative flex h-9 w-9 items-center justify-center rounded-xl bg-gradient-to-br from-emerald-500 to-emerald-600 shadow-lg shadow-emerald-500/20 transition-all group-hover:scale-105 group-hover:shadow-emerald-500/30">
                <svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="white" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
                  <path d="M13 2L3 14h9l-1 8 10-12h-9l1-8z" />
                </svg>
              </div>
              <span className="text-lg font-bold bg-gradient-to-r from-gray-900 to-gray-700 dark:from-white dark:to-gray-200 bg-clip-text text-transparent">
                Spark
              </span>
            </Link>
            
            {/* 分割线 */}
            <div className="hidden md:block h-6 w-px bg-border" />
            
            {/* 主导航链接 */}
            <div className="hidden md:flex items-center gap-1">
              {navItems.map((item) => (
                <Link
                  key={item.href}
                  href={item.href}
                  className={cn(
                    "flex items-center gap-2 px-3.5 py-2 rounded-lg text-sm font-medium transition-all duration-200",
                    isActive(item.href)
                      ? "bg-primary/10 text-primary"
                      : "text-muted-foreground hover:bg-muted hover:text-foreground"
                  )}
                >
                  {item.icon}
                  <span>{item.name}</span>
                </Link>
              ))}
            </div>
          </div>

          {/* 右侧：系统状态 + 操作按钮 */}
          <div className="flex items-center gap-3">
            {/* 系统状态指示器 */}
            {!isLoading && (
              <div className="hidden sm:flex items-center gap-2 px-3 py-1.5 rounded-full bg-muted/50 text-xs font-medium">
                {/* 模型状态 */}
                <div className="flex items-center gap-1.5">
                  <div className="w-1.5 h-1.5 rounded-full bg-emerald-500 animate-pulse" />
                  <span className="text-muted-foreground">
                    {systemStatus.selectedModel ? (
                      <span className="text-foreground">{systemStatus.selectedModel}</span>
                    ) : (
                      "未选择模型"
                    )}
                  </span>
                </div>
                
                <div className="w-px h-3 bg-border" />
                
                {/* 知识源数量 */}
                <div className="flex items-center gap-1 text-muted-foreground">
                  <svg xmlns="http://www.w3.org/2000/svg" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                    <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
                    <path d="M14 2v6h6" />
                  </svg>
                  <span>{systemStatus.selectedSourcesCount}</span>
                </div>
                
                <div className="w-px h-3 bg-border" />
                
                {/* 向量数量 */}
                <div className="flex items-center gap-1 text-muted-foreground">
                  <svg xmlns="http://www.w3.org/2000/svg" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                    <path d="M21 16V8a2 2 0 0 0-1-1.73l-7-4a2 2 0 0 0-2 0l-7 4A2 2 0 0 0 3 8v8a2 2 0 0 0 1 1.73l7 4a2 2 0 0 0 2 0l7-4A2 2 0 0 0 21 16z" />
                  </svg>
                  <span>{(systemStatus.totalVectors / 1000).toFixed(1)}k</span>
                </div>
              </div>
            )}
            
            {/* 新建对话按钮 - 作为操作按钮而不是导航项 */}
            <Link
              href="/"
              className="flex items-center gap-2 px-4 py-2 rounded-lg bg-primary text-primary-foreground text-sm font-medium shadow-lg shadow-primary/25 hover:bg-primary/90 transition-all duration-200 hover:scale-105"
            >
              <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <path d="M12 5v14M5 12h14" />
              </svg>
              <span className="hidden sm:inline">新建对话</span>
            </Link>
          </div>
        </div>
      </nav>

      {/* 移动端导航 */}
      <nav className="fixed bottom-0 left-0 right-0 z-50 md:hidden h-16 border-t border-border/50 bg-background/95 backdrop-blur-xl">
        <div className="flex h-full items-center justify-around px-2">
          {navItems.map((item) => (
            <Link
              key={item.href}
              href={item.href}
              className={cn(
                "flex flex-col items-center gap-1 px-4 py-2 rounded-lg transition-colors",
                isActive(item.href)
                  ? "text-primary"
                  : "text-muted-foreground"
              )}
            >
              {item.icon}
              <span className="text-xs font-medium">{item.name}</span>
            </Link>
          ))}
        </div>
      </nav>
    </>
  );
}

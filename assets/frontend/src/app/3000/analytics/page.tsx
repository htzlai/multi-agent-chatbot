/*
# SPDX-FileCopyrightText: Copyright (c) 1993-2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
*/

"use client";

import { useState, useEffect, useCallback, useMemo } from "react";
import Link from "next/link";
import {
  LineChart,
  Line,
  AreaChart,
  Area,
  BarChart,
  Bar,
  PieChart,
  Pie,
  Cell,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  Legend,
} from "recharts";

// ============== Configuration ==============
const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

// ============== Types ==============
interface AnalyticsData {
  total_queries: number;
  total_chats: number;
  total_sources: number;
  total_vectors: number;
  queries_today: number;
  queries_this_week: number;
  queries_this_month: number;
  avg_response_time: number;
  cache_hit_rate: number;
  popular_queries: Array<{ query: string; count: number }>;
  daily_queries: Array<{ date: string; count: number; avg_time: number }>;
  source_usage: Array<{ name: string; value: number; color: string }>;
  chat_sessions: Array<{ date: string; sessions: number; messages: number }>;
}

interface SystemMetrics {
  cpu_usage: number;
  memory_usage: number;
  disk_usage: number;
  network_in: number;
  network_out: number;
  uptime: number;
}

interface ModelUsage {
  model_id: string;
  requests: number;
  tokens: number;
  avg_latency: number;
}

// ============== Icons ==============
const Icons = {
  Chart: () => (
    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
      <path d="M3 3v18h18" />
      <path d="M18 17V9" />
      <path d="M13 17V5" />
      <path d="M8 17v-3" />
    </svg>
  ),
  Activity: () => (
    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
      <polyline points="22 12 18 12 15 21 9 3 6 12 2 12" />
    </svg>
  ),
  Users: () => (
    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
      <path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2" />
      <circle cx="9" cy="7" r="4" />
      <path d="M23 21v-2a4 4 0 0 0-3-3.87" />
      <path d="M16 3.13a4 4 0 0 1 0 7.75" />
    </svg>
  ),
  Clock: () => (
    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
      <circle cx="12" cy="12" r="10" />
      <polyline points="12 6 12 12 16 14" />
    </svg>
  ),
  Database: () => (
    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
      <ellipse cx="12" cy="5" rx="9" ry="3" />
      <path d="M21 12c0 1.66-4 3-9 3s-9-1.34-9-3" />
      <path d="M3 5v14c0 1.66 4 3 9 3s9-1.34 9-3V5" />
    </svg>
  ),
  Zap: ({ className }: { className?: string }) => (
    <svg className={className} width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
      <polygon points="13 2 3 14 12 14 11 22 21 10 12 10 13 2" />
    </svg>
  ),
  Refresh: () => (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
      <path d="M23 4v6h-6M1 20v-6h6" />
      <path d="M3.51 9a9 9 0 0 1 14.85-3.36L23 10M1 14l4.64 4.36A9 9 0 0 0 20.49 15" />
    </svg>
  ),
  ArrowLeft: () => (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
      <path d="M19 12H5M12 19l-7-7 7-7" />
    </svg>
  ),
  TrendingUp: () => (
    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
      <polyline points="23 6 13.5 15.5 8.5 10.5 1 18" />
      <polyline points="17 6 23 6 23 12" />
    </svg>
  ),
  TrendingDown: () => (
    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
      <polyline points="23 18 13.5 8.5 8.5 13.5 1 6" />
      <polyline points="17 18 23 18 23 12" />
    </svg>
  ),
  Target: () => (
    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
      <circle cx="12" cy="12" r="10" />
      <circle cx="12" cy="12" r="6" />
      <circle cx="12" cy="12" r="2" />
    </svg>
  ),
  Cpu: () => (
    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
      <rect x="4" y="4" width="16" height="16" rx="2" ry="2" />
      <rect x="9" y="9" width="6" height="6" />
      <path d="M9 1v3M15 1v3M9 20v3M15 20v3M20 9h3M20 14h3M1 9h3M1 14h3" />
    </svg>
  ),
  HardDrive: () => (
    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
      <line x1="22" y1="12" x2="2" y2="12" />
      <path d="M5.45 5.11L2 12v6a2 2 0 0 0 2 2h16a2 2 0 0 0 2-2v-6l-3.45-6.89A2 2 0 0 0 16.76 4H7.24a2 2 0 0 0-1.79 1.11z" />
      <line x1="6" y1="16" x2="6.01" y2="16" />
      <line x1="10" y1="16" x2="10.01" y2="16" />
    </svg>
  ),
  Wifi: () => (
    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
      <path d="M5 12.55a11 11 0 0 1 14.08 0" />
      <path d="M1.42 9a16 16 0 0 1 21.16 0" />
      <path d="M8.53 16.11a6 6 0 0 1 6.95 0" />
      <line x1="12" y1="20" x2="12.01" y2="20" />
    </svg>
  ),
  Check: () => (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
      <polyline points="20 6 9 17 4 12" />
    </svg>
  ),
  AlertCircle: () => (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
      <circle cx="12" cy="12" r="10" />
      <line x1="12" y1="8" x2="12" y2="12" />
      <line x1="12" y1="16" x2="12.01" y2="16" />
    </svg>
  ),
  Info: () => (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
      <circle cx="12" cy="12" r="10" />
      <line x1="12" y1="16" x2="12" y2="12" />
      <line x1="12" y1="8" x2="12.01" y2="8" />
    </svg>
  ),
  Calendar: () => (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
      <rect x="3" y="4" width="18" height="18" rx="2" ry="2" />
      <line x1="16" y1="2" x2="16" y2="6" />
      <line x1="8" y1="2" x2="8" y2="6" />
      <line x1="3" y1="10" x2="21" y2="10" />
    </svg>
  ),
  FileText: () => (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
      <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
      <polyline points="14 2 14 8 20 8" />
      <line x1="16" y1="13" x2="8" y2="13" />
      <line x1="16" y1="17" x2="8" y2="17" />
      <polyline points="10 9 9 9 8 9" />
    </svg>
  ),
  Search: () => (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
      <circle cx="11" cy="11" r="8" />
      <line x1="21" y1="21" x2="16.65" y2="16.65" />
    </svg>
  ),
  Bot: () => (
    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
      <rect x="3" y="11" width="18" height="10" rx="2" />
      <circle cx="12" cy="5" r="2" />
      <path d="M12 7v4" />
      <line x1="8" y1="16" x2="8" y2="16" />
      <line x1="16" y1="16" x2="16" y2="16" />
    </svg>
  ),
  MessageSquare: () => (
    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
      <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z" />
    </svg>
  ),
};

// ============== Colors ==============
const COLORS = {
  emerald: "#10b981",
  cyan: "#06b6d4",
  violet: "#8b5cf6",
  amber: "#f59e0b",
  rose: "#f43f5e",
  blue: "#3b82f6",
  indigo: "#6366f1",
  teal: "#14b8a6",
};

const CHART_COLORS = [COLORS.emerald, COLORS.cyan, COLORS.violet, COLORS.amber, COLORS.rose, COLORS.blue];

// ============== Utility Functions ==============
const formatNumber = (num: number): string => {
  if (num >= 1000000) return (num / 1000000).toFixed(1) + "M";
  if (num >= 1000) return (num / 1000).toFixed(1) + "K";
  return num.toString();
};

const formatUptime = (seconds: number): string => {
  const days = Math.floor(seconds / 86400);
  const hours = Math.floor((seconds % 86400) / 3600);
  const mins = Math.floor((seconds % 3600) / 60);
  return `${days}d ${hours}h ${mins}m`;
};

const formatBytes = (bytes: number): string => {
  if (bytes >= 1073741824) return (bytes / 1073741824).toFixed(2) + " GB";
  if (bytes >= 1048576) return (bytes / 1048576).toFixed(2) + " MB";
  if (bytes >= 1024) return (bytes / 1024).toFixed(2) + " KB";
  return bytes + " B";
};

// ============== Main Component ==============
export default function AnalyticsPage() {
  const [isLoading, setIsLoading] = useState(true);
  const [timeRange, setTimeRange] = useState<"24h" | "7d" | "30d" | "90d">("7d");
  const [analyticsData, setAnalyticsData] = useState<AnalyticsData | null>(null);
  const [systemMetrics, setSystemMetrics] = useState<SystemMetrics | null>(null);
  const [modelUsage, setModelUsage] = useState<ModelUsage[]>([]);
  const [currentTime, setCurrentTime] = useState(new Date());

  // Update time
  useEffect(() => {
    const timer = setInterval(() => setCurrentTime(new Date()), 1000);
    return () => clearInterval(timer);
  }, []);

  // Fetch analytics data
  const fetchAnalyticsData = useCallback(async () => {
    try {
      // Mock data for demonstration - replace with actual API calls
      const mockAnalytics: AnalyticsData = {
        total_queries: 12847,
        total_chats: 342,
        total_sources: 12,
        total_vectors: 2458923,
        queries_today: 156,
        queries_this_week: 1234,
        queries_this_month: 5678,
        avg_response_time: 1.23,
        cache_hit_rate: 78.5,
        popular_queries: [
          { query: "How to optimize GPU performance?", count: 234 },
          { query: "Best practices for RAG implementation", count: 189 },
          { query: "NVIDIA DGX system specifications", count: 156 },
          { query: "Troubleshooting memory issues", count: 134 },
          { query: "Deployment guide for models", count: 112 },
        ],
        daily_queries: Array.from({ length: 30 }, (_, i) => ({
          date: new Date(Date.now() - (29 - i) * 86400000).toLocaleDateString("en-US", { month: "short", day: "numeric" }),
          count: Math.floor(Math.random() * 200) + 50,
          avg_time: Math.random() * 2 + 0.5,
        })),
        source_usage: [
          { name: "API Documentation", value: 35, color: COLORS.emerald },
          { name: "User Guides", value: 25, color: COLORS.cyan },
          { name: "Technical Docs", value: 20, color: COLORS.violet },
          { name: "FAQs", value: 12, color: COLORS.amber },
          { name: "Others", value: 8, color: COLORS.rose },
        ],
        chat_sessions: Array.from({ length: 14 }, (_, i) => ({
          date: new Date(Date.now() - (13 - i) * 86400000).toLocaleDateString("en-US", { weekday: "short" }),
          sessions: Math.floor(Math.random() * 50) + 10,
          messages: Math.floor(Math.random() * 200) + 50,
        })),
      };

      const mockMetrics: SystemMetrics = {
        cpu_usage: 45 + Math.random() * 20,
        memory_usage: 62 + Math.random() * 15,
        disk_usage: 38 + Math.random() * 10,
        network_in: Math.random() * 1000,
        network_out: Math.random() * 500,
        uptime: 86400 * 7 + Math.random() * 86400,
      };

      const mockModelUsage: ModelUsage[] = [
        { model_id: "llama-3.1-70b", requests: 4521, tokens: 2345678, avg_latency: 1.23 },
        { model_id: "llama-3.1-8b", requests: 8234, tokens: 4567890, avg_latency: 0.45 },
        { model_id: "mixtral-8x7b", requests: 1234, tokens: 1234567, avg_latency: 0.89 },
      ];

      setAnalyticsData(mockAnalytics);
      setSystemMetrics(mockMetrics);
      setModelUsage(mockModelUsage);
    } catch (err) {
      console.error("Error fetching analytics:", err);
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchAnalyticsData();
    const interval = setInterval(fetchAnalyticsData, 30000);
    return () => clearInterval(interval);
  }, [fetchAnalyticsData]);

  // Calculate stats
  const stats = useMemo(() => {
    if (!analyticsData) return null;
    return {
      queryGrowth: ((analyticsData.queries_this_week - analyticsData.queries_today) / analyticsData.queries_today * 100).toFixed(1),
      avgResponseTrend: analyticsData.avg_response_time > 1 ? "up" : "down",
      cacheHitTrend: analyticsData.cache_hit_rate > 70 ? "up" : "down",
    };
  }, [analyticsData]);

  // Render loading state
  if (isLoading) {
    return (
      <div className="min-h-screen bg-gradient-to-br from-slate-900 via-slate-800 to-slate-900 flex items-center justify-center">
        <div className="text-center">
          <div className="relative mb-8">
            <div className="w-20 h-20 border-4 border-emerald-500/30 rounded-full animate-spin border-t-emerald-500"></div>
            <div className="absolute inset-0 flex items-center justify-center">
              <Icons.Chart />
            </div>
          </div>
          <p className="text-slate-400 text-lg">Loading Analytics...</p>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-900 via-slate-800 to-slate-900">
      {/* Header */}
      <header className="sticky top-0 z-40 bg-slate-900/80 backdrop-blur-xl border-b border-slate-700/50">
        <div className="flex h-16 items-center justify-between px-4 lg:px-6">
          <div className="flex items-center gap-3">
            <div className="flex items-center gap-2">
              <div className="flex h-9 w-9 items-center justify-center rounded-xl bg-gradient-to-br from-violet-500 to-violet-600 shadow-lg shadow-violet-500/20">
                <Icons.Chart className="text-white" />
              </div>
              <span className="text-lg font-bold text-white">Analytics</span>
            </div>
          </div>

          <div className="flex items-center gap-3">
            {/* Time Range Selector */}
            <div className="flex items-center bg-slate-800/50 rounded-lg p-1">
              {(["24h", "7d", "30d", "90d"] as const).map((range) => (
                <button
                  key={range}
                  onClick={() => setTimeRange(range)}
                  className={`px-3 py-1.5 text-sm rounded-md transition-all ${
                    timeRange === range
                      ? "bg-violet-600 text-white"
                      : "text-slate-400 hover:text-white hover:bg-slate-700"
                  }`}
                >
                  {range}
                </button>
              ))}
            </div>

            <button
              onClick={fetchAnalyticsData}
              className="p-2 rounded-lg hover:bg-slate-700/50 text-slate-400 hover:text-white transition-colors"
            >
              <Icons.Refresh />
            </button>

            <Link
              href="/3000/chat"
              className="flex items-center gap-2 px-3 py-2 rounded-lg bg-slate-800/50 text-slate-400 hover:text-white hover:bg-slate-700/50 transition-colors text-sm"
            >
              <Icons.ArrowLeft />
              <span className="hidden sm:inline">Back</span>
            </Link>
          </div>
        </div>
      </header>

      <main className="p-6 max-w-7xl mx-auto">
        {/* Stats Grid */}
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4 mb-6">
          {/* Total Queries */}
          <div className="bg-gradient-to-br from-slate-800 to-slate-800/50 rounded-xl border border-slate-700/50 p-5 hover:border-violet-500/30 transition-colors group">
            <div className="flex items-center justify-between mb-3">
              <div className="p-2 rounded-lg bg-violet-500/20">
                <Icons.Search className="text-violet-400" />
              </div>
              <span className="text-xs text-emerald-400 flex items-center gap-1">
                <Icons.TrendingUp className="w-3 h-3" />
                +12.5%
              </span>
            </div>
            <div className="text-3xl font-bold text-white mb-1">
              {formatNumber(analyticsData?.total_queries || 0)}
            </div>
            <div className="text-sm text-slate-400">Total Queries</div>
          </div>

          {/* Active Chats */}
          <div className="bg-gradient-to-br from-slate-800 to-slate-800/50 rounded-xl border border-slate-700/50 p-5 hover:border-cyan-500/30 transition-colors group">
            <div className="flex items-center justify-between mb-3">
              <div className="p-2 rounded-lg bg-cyan-500/20">
                <Icons.MessageSquare className="text-cyan-400" />
              </div>
              <span className="text-xs text-emerald-400 flex items-center gap-1">
                <Icons.TrendingUp className="w-3 h-3" />
                +8.2%
              </span>
            </div>
            <div className="text-3xl font-bold text-white mb-1">
              {analyticsData?.total_chats || 0}
            </div>
            <div className="text-sm text-slate-400">Chat Sessions</div>
          </div>

          {/* Avg Response Time */}
          <div className="bg-gradient-to-br from-slate-800 to-slate-800/50 rounded-xl border border-slate-700/50 p-5 hover:border-emerald-500/30 transition-colors group">
            <div className="flex items-center justify-between mb-3">
              <div className="p-2 rounded-lg bg-emerald-500/20">
                <Icons.Activity className="text-emerald-400" />
              </div>
              <span className={`text-xs flex items-center gap-1 ${
                stats?.avgResponseTrend === "down" ? "text-emerald-400" : "text-red-400"
              }`}>
                {stats?.avgResponseTrend === "down" ? (
                  <Icons.TrendingDown className="w-3 h-3" />
                ) : (
                  <Icons.TrendingUp className="w-3 h-3" />
                )}
                -5.3%
              </span>
            </div>
            <div className="text-3xl font-bold text-white mb-1">
              {analyticsData?.avg_response_time?.toFixed(2) || 0}s
            </div>
            <div className="text-sm text-slate-400">Avg Response Time</div>
          </div>

          {/* Cache Hit Rate */}
          <div className="bg-gradient-to-br from-slate-800 to-slate-800/50 rounded-xl border border-slate-700/50 p-5 hover:border-amber-500/30 transition-colors group">
            <div className="flex items-center justify-between mb-3">
              <div className="p-2 rounded-lg bg-amber-500/20">
                <Icons.Database className="text-amber-400" />
              </div>
              <span className={`text-xs flex items-center gap-1 ${
                stats?.cacheHitTrend === "up" ? "text-emerald-400" : "text-red-400"
              }`}>
                {stats?.cacheHitTrend === "up" ? (
                  <Icons.TrendingUp className="w-3 h-3" />
                ) : (
                  <Icons.TrendingDown className="w-3 h-3" />
                )}
                +2.1%
              </span>
            </div>
            <div className="text-3xl font-bold text-white mb-1">
              {analyticsData?.cache_hit_rate?.toFixed(1) || 0}%
            </div>
            <div className="text-sm text-slate-400">Cache Hit Rate</div>
          </div>
        </div>

        {/* Charts Row 1 */}
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-6">
          {/* Query Volume Chart */}
          <div className="bg-slate-800/50 rounded-xl border border-slate-700/50 p-6">
            <div className="flex items-center justify-between mb-6">
              <h3 className="text-lg font-semibold text-white flex items-center gap-2">
                <Icons.Activity className="text-violet-400" />
                Query Volume
              </h3>
              <div className="text-sm text-slate-400">
                Last {timeRange === "24h" ? "24 hours" : timeRange === "7d" ? "7 days" : timeRange === "30d" ? "30 days" : "90 days"}
              </div>
            </div>
            <div className="h-64">
              <ResponsiveContainer width="100%" height="100%">
                <AreaChart data={analyticsData?.daily_queries || []}>
                  <defs>
                    <linearGradient id="colorQueries" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="5%" stopColor={COLORS.violet} stopOpacity={0.3} />
                      <stop offset="95%" stopColor={COLORS.violet} stopOpacity={0} />
                    </linearGradient>
                  </defs>
                  <CartesianGrid strokeDasharray="3 3" stroke="#334155" />
                  <XAxis 
                    dataKey="date" 
                    stroke="#64748b" 
                    fontSize={12}
                    tickLine={false}
                  />
                  <YAxis 
                    stroke="#64748b" 
                    fontSize={12}
                    tickLine={false}
                    axisLine={false}
                  />
                  <Tooltip
                    contentStyle={{
                      backgroundColor: "#1e293b",
                      border: "1px solid #334155",
                      borderRadius: "8px",
                      color: "#fff",
                    }}
                  />
                  <Area
                    type="monotone"
                    dataKey="count"
                    stroke={COLORS.violet}
                    strokeWidth={2}
                    fillOpacity={1}
                    fill="url(#colorQueries)"
                    name="Queries"
                  />
                </AreaChart>
              </ResponsiveContainer>
            </div>
          </div>

          {/* Response Time Chart */}
          <div className="bg-slate-800/50 rounded-xl border border-slate-700/50 p-6">
            <div className="flex items-center justify-between mb-6">
              <h3 className="text-lg font-semibold text-white flex items-center gap-2">
                <Icons.Clock className="text-cyan-400" />
                Response Time
              </h3>
              <div className="text-sm text-slate-400">Average over time</div>
            </div>
            <div className="h-64">
              <ResponsiveContainer width="100%" height="100%">
                <LineChart data={analyticsData?.daily_queries || []}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#334155" />
                  <XAxis 
                    dataKey="date" 
                    stroke="#64748b" 
                    fontSize={12}
                    tickLine={false}
                  />
                  <YAxis 
                    stroke="#64748b" 
                    fontSize={12}
                    tickLine={false}
                    axisLine={false}
                    unit="s"
                  />
                  <Tooltip
                    contentStyle={{
                      backgroundColor: "#1e293b",
                      border: "1px solid #334155",
                      borderRadius: "8px",
                      color: "#fff",
                    }}
                  />
                  <Line
                    type="monotone"
                    dataKey="avg_time"
                    stroke={COLORS.cyan}
                    strokeWidth={2}
                    dot={{ fill: COLORS.cyan, strokeWidth: 2, r: 4 }}
                    activeDot={{ r: 6, fill: COLORS.cyan }}
                    name="Avg Time (s)"
                  />
                </LineChart>
              </ResponsiveContainer>
            </div>
          </div>
        </div>

        {/* Charts Row 2 */}
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6 mb-6">
          {/* Source Usage Pie Chart */}
          <div className="bg-slate-800/50 rounded-xl border border-slate-700/50 p-6">
            <h3 className="text-lg font-semibold text-white flex items-center gap-2 mb-6">
              <Icons.FileText className="text-emerald-400" />
              Source Usage
            </h3>
            <div className="h-48">
              <ResponsiveContainer width="100%" height="100%">
                <PieChart>
                  <Pie
                    data={analyticsData?.source_usage || []}
                    cx="50%"
                    cy="50%"
                    innerRadius={50}
                    outerRadius={80}
                    paddingAngle={2}
                    dataKey="value"
                  >
                    {(analyticsData?.source_usage || []).map((entry, index) => (
                      <Cell key={`cell-${index}`} fill={entry.color} />
                    ))}
                  </Pie>
                  <Tooltip
                    contentStyle={{
                      backgroundColor: "#1e293b",
                      border: "1px solid #334155",
                      borderRadius: "8px",
                      color: "#fff",
                    }}
                    formatter={(value: number) => [`${value}%`, "Usage"]}
                  />
                </PieChart>
              </ResponsiveContainer>
            </div>
            <div className="flex flex-wrap justify-center gap-3 mt-4">
              {(analyticsData?.source_usage || []).map((source, idx) => (
                <div key={idx} className="flex items-center gap-1.5">
                  <div
                    className="w-2.5 h-2.5 rounded-full"
                    style={{ backgroundColor: source.color }}
                  />
                  <span className="text-xs text-slate-400">{source.name}</span>
                </div>
              ))}
            </div>
          </div>

          {/* Chat Sessions Bar Chart */}
          <div className="bg-slate-800/50 rounded-xl border border-slate-700/50 p-6 lg:col-span-2">
            <h3 className="text-lg font-semibold text-white flex items-center gap-2 mb-6">
              <Icons.Users className="text-amber-400" />
              Chat Sessions
            </h3>
            <div className="h-48">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={analyticsData?.chat_sessions || []}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#334155" />
                  <XAxis 
                    dataKey="date" 
                    stroke="#64748b" 
                    fontSize={12}
                    tickLine={false}
                  />
                  <YAxis 
                    stroke="#64748b" 
                    fontSize={12}
                    tickLine={false}
                    axisLine={false}
                  />
                  <Tooltip
                    contentStyle={{
                      backgroundColor: "#1e293b",
                      border: "1px solid #334155",
                      borderRadius: "8px",
                      color: "#fff",
                    }}
                  />
                  <Bar dataKey="sessions" fill={COLORS.amber} radius={[4, 4, 0, 0]} name="Sessions" />
                  <Bar dataKey="messages" fill={COLORS.emerald} radius={[4, 4, 0, 0]} name="Messages" />
                </BarChart>
              </ResponsiveContainer>
            </div>
          </div>
        </div>

        {/* System Metrics & Model Usage */}
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          {/* System Metrics */}
          <div className="bg-slate-800/50 rounded-xl border border-slate-700/50 p-6">
            <h3 className="text-lg font-semibold text-white flex items-center gap-2 mb-6">
              <Icons.Cpu className="text-blue-400" />
              System Resources
            </h3>
            <div className="space-y-4">
              {/* CPU */}
              <div>
                <div className="flex justify-between text-sm mb-2">
                  <span className="text-slate-400">CPU Usage</span>
                  <span className="text-white font-medium">{systemMetrics?.cpu_usage?.toFixed(1)}%</span>
                </div>
                <div className="h-2 bg-slate-700 rounded-full overflow-hidden">
                  <div
                    className="h-full bg-gradient-to-r from-blue-500 to-cyan-500 rounded-full transition-all duration-500"
                    style={{ width: `${systemMetrics?.cpu_usage || 0}%` }}
                  />
                </div>
              </div>
              {/* Memory */}
              <div>
                <div className="flex justify-between text-sm mb-2">
                  <span className="text-slate-400">Memory Usage</span>
                  <span className="text-white font-medium">{systemMetrics?.memory_usage?.toFixed(1)}%</span>
                </div>
                <div className="h-2 bg-slate-700 rounded-full overflow-hidden">
                  <div
                    className="h-full bg-gradient-to-r from-violet-500 to-pink-500 rounded-full transition-all duration-500"
                    style={{ width: `${systemMetrics?.memory_usage || 0}%` }}
                  />
                </div>
              </div>
              {/* Disk */}
              <div>
                <div className="flex justify-between text-sm mb-2">
                  <span className="text-slate-400">Disk Usage</span>
                  <span className="text-white font-medium">{systemMetrics?.disk_usage?.toFixed(1)}%</span>
                </div>
                <div className="h-2 bg-slate-700 rounded-full overflow-hidden">
                  <div
                    className="h-full bg-gradient-to-r from-amber-500 to-red-500 rounded-full transition-all duration-500"
                    style={{ width: `${systemMetrics?.disk_usage || 0}%` }}
                  />
                </div>
              </div>
              {/* Network */}
              <div className="grid grid-cols-2 gap-4 pt-2">
                <div className="bg-slate-900/50 rounded-lg p-3">
                  <div className="flex items-center gap-2 text-slate-400 text-xs mb-1">
                    <Icons.Wifi className="w-3 h-3" />
                    Network In
                  </div>
                  <div className="text-lg font-semibold text-white">
                    {formatBytes(systemMetrics?.network_in || 0)}/s
                  </div>
                </div>
                <div className="bg-slate-900/50 rounded-lg p-3">
                  <div className="flex items-center gap-2 text-slate-400 text-xs mb-1">
                    <Icons.Wifi className="w-3 h-3" />
                    Network Out
                  </div>
                  <div className="text-lg font-semibold text-white">
                    {formatBytes(systemMetrics?.network_out || 0)}/s
                  </div>
                </div>
              </div>
              {/* Uptime */}
              <div className="bg-slate-900/50 rounded-lg p-3">
                <div className="flex items-center gap-2 text-slate-400 text-xs mb-1">
                  <Icons.Clock className="w-3 h-3" />
                  System Uptime
                </div>
                <div className="text-lg font-semibold text-emerald-400">
                  {formatUptime(systemMetrics?.uptime || 0)}
                </div>
              </div>
            </div>
          </div>

          {/* Model Usage */}
          <div className="bg-slate-800/50 rounded-xl border border-slate-700/50 p-6">
            <h3 className="text-lg font-semibold text-white flex items-center gap-2 mb-6">
              <Icons.Bot className="text-rose-400" />
              Model Usage
            </h3>
            <div className="space-y-3">
              {modelUsage.map((model, idx) => (
                <div
                  key={idx}
                  className="bg-slate-900/50 rounded-lg p-4 border border-slate-700/50 hover:border-rose-500/30 transition-colors"
                >
                  <div className="flex items-center justify-between mb-3">
                    <div className="flex items-center gap-2">
                      <div className="w-8 h-8 rounded-lg bg-rose-500/20 flex items-center justify-center">
                        <Icons.Bot className="w-4 h-4 text-rose-400" />
                      </div>
                      <span className="text-sm font-medium text-white truncate max-w-[180px]">
                        {model.model_id}
                      </span>
                    </div>
                    <span className="text-xs text-slate-500">
                      {formatNumber(model.requests)} requests
                    </span>
                  </div>
                  <div className="grid grid-cols-2 gap-3 text-sm">
                    <div>
                      <span className="text-slate-500">Tokens</span>
                      <div className="text-white font-medium">{formatNumber(model.tokens)}</div>
                    </div>
                    <div>
                      <span className="text-slate-500">Avg Latency</span>
                      <div className="text-emerald-400 font-medium">{model.avg_latency}s</div>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>

        {/* Popular Queries */}
        <div className="mt-6 bg-slate-800/50 rounded-xl border border-slate-700/50 p-6">
          <h3 className="text-lg font-semibold text-white flex items-center gap-2 mb-6">
            <Icons.Target className="text-violet-400" />
            Popular Queries
          </h3>
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
            {(analyticsData?.popular_queries || []).map((item, idx) => (
              <div
                key={idx}
                className="bg-slate-900/50 rounded-lg p-4 border border-slate-700/50 hover:border-violet-500/30 transition-all hover:translate-y-[-2px]"
              >
                <div className="flex items-center gap-2 mb-2">
                  <span className="w-6 h-6 rounded-full bg-violet-500/20 text-violet-400 flex items-center justify-center text-xs font-bold">
                    {idx + 1}
                  </span>
                  <span className="text-xs text-slate-500">{item.count} queries</span>
                </div>
                <p className="text-sm text-white line-clamp-2">{item.query}</p>
              </div>
            ))}
          </div>
        </div>
      </main>
    </div>
  );
}

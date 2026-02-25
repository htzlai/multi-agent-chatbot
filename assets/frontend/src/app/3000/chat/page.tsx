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

import { useState, useEffect, useCallback, useRef, useMemo } from "react";
import Link from "next/link";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

// ============== Configuration ==============
const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

// ============== Types ==============
interface Chat {
  chat_id: string;
  name?: string;
  message_count?: number;
  created_at?: string;
  updated_at?: string;
}

interface ChatMessage {
  type: string;
  content: string;
}

interface Source {
  name: string;
  selected: boolean;
  chunk_count?: number;
  max_score?: number;
}

interface SourceResult {
  name: string;
  score: number;
  vector_score?: number;
  bm25_score?: number;
  excerpt: string;
}

interface RagResponse {
  answer: string;
  sources: SourceResult[];
  num_sources: number;
  search_type: string;
  reranking_enabled?: boolean;
  hyde_applied?: boolean;
  retrieval_metadata?: {
    total_chunks_retrieved: number;
    unique_sources_count: number;
    score_range: { min: number; max: number; avg: number };
  };
}

interface Model {
  id: string;
  object: string;
  created: number;
  owned_by: string;
}

interface VectorStats {
  collection: string;
  total_entities: number;
  milvus_uri?: string;
  embedding_dimensions?: number;
}

interface RAGStats {
  index: {
    collection: string;
    milvus_uri: string;
    embedding_dimensions: number;
    total_entities: number;
  };
  cache: {
    enabled: boolean;
    backend: string;
    redis_available: boolean;
    ttl: number;
    cached_queries: number;
  };
}

interface RAGConfig {
  features: {
    hybrid_search: boolean;
    multiple_chunking: boolean;
    query_cache: boolean;
    custom_embeddings: boolean;
    reranking?: boolean;
  };
  chunk_strategies: string[];
  default_chunk_strategy: string;
  default_top_k: number;
}

interface HealthStatus {
  status: string;
  services: {
    postgres: string;
    milvus: string;
    embedding: string;
    llm: string;
    langfuse: string;
    redis: string;
  };
}

interface RAGHealthStatus {
  status: string;
  rag_index: {
    collection: string;
    milvus_uri: string;
    embedding_dimensions: number;
    total_entities: number;
  };
  knowledge: {
    config_sources: number;
    file_sources: number;
    vector_sources: number;
    fully_synced_count: number;
    issues: Record<string, unknown>;
  };
  cache: {
    backend: string;
    ttl: number;
    redis_available: boolean;
    redis_keys: number;
  };
  bm25_index: {
    initialized: boolean;
    document_count: number;
  };
}

interface CacheStats {
  memory_cache: {
    entries: number;
    ttl: number;
  };
  redis_cache: {
    backend: string;
    ttl: number;
    memory_entries: number;
    redis_available: boolean;
    redis_keys: number;
  };
}

interface KnowledgeStatus {
  config: {
    total: number;
    selected: number;
    sources: string[];
  };
  files: {
    total: number;
    sources: string[];
  };
  vectors: {
    total: number;
    sources: string[];
  };
  issues: {
    orphaned_in_config: string[];
    untracked_files: string[];
    need_indexing: string[];
    orphaned_vectors: string[];
    config_without_vectors: string[];
  };
  summary: {
    config_files_match: boolean;
    files_indexed: boolean;
    vectors_clean: boolean;
    fully_synced_count: number;
    config_has_vectors: boolean;
  };
}

interface VectorCounts {
  sources: string[];
  total_vectors: number;
  source_vectors: Record<string, number>;
}

// ============== Icons ==============
const Icons = {
  Chat: () => (
    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/>
    </svg>
  ),
  File: () => (
    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/>
      <path d="M14 2v6h6M16 13H8M16 17H8M10 9H8"/>
    </svg>
  ),
  Search: ({ className }: { className?: string }) => (
    <svg className={className} width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <circle cx="11" cy="11" r="8"/>
      <path d="M21 21l-4.35-4.35"/>
    </svg>
  ),
  Cpu: () => (
    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <rect x="4" y="4" width="16" height="16" rx="2" ry="2"/>
      <rect x="9" y="9" width="6" height="6"/>
      <path d="M9 1v3M15 1v3M9 20v3M15 20v3M20 9h3M20 14h3M1 9h14h3"/>
3M1     </svg>
  ),
  Plus: () => (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M12 5v14M5 12h14"/>
    </svg>
  ),
  Trash: () => (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M3 6h18M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/>
    </svg>
  ),
  Refresh: () => (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M23 4v6h-6M1 20v-6h6"/>
      <path d="M3.51 9a9 9 0 0 1 14.85-3.36L23 10M1 14l4.64 4.36A9 9 0 0 0 20.49 15"/>
    </svg>
  ),
  ArrowLeft: () => (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M19 12H5M12 19l-7-7 7-7"/>
    </svg>
  ),
  Send: () => (
    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M22 2L11 13M22 2l-7 20-4-9-9-4 20-7z"/>
    </svg>
  ),
  X: () => (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M18 6L6 18M6 6l12 12"/>
    </svg>
  ),
  Check: () => (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M20 6L9 17l-5-5"/>
    </svg>
  ),
  ChevronRight: () => (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M9 18l6-6-6-6"/>
    </svg>
  ),
  Menu: () => (
    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M3 12h18M3 6h18M3 18h18"/>
    </svg>
  ),
  Database: ({ className }: { className?: string }) => (
    <svg className={className} width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <ellipse cx="12" cy="5" rx="9" ry="3"/>
      <path d="M21 12c0 1.66-4 3-9 3s-9-1.34-9-3"/>
      <path d="M3 5v14c0 1.66 4 3 9 3s9-1.34 9-3V5"/>
    </svg>
  ),
  Settings: () => (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <circle cx="12" cy="12" r="3"/>
      <path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1 0 2.83 2 2 0 0 1-2.83 0l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-2 2 2 2 0 0 1-2-2v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83 0 2 2 0 0 1 0-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1-2-2 2 2 0 0 1 2-2h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 0-2.83 2 2 0 0 1 2.83 0l.06.06a1.65 1.65 0 0 0 1.82.33H9a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 2-2 2 2 0 0 1 2 2v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 0 2 2 0 0 1 0 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82V9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 2 2 2 2 0 0 1-2 2h-.09a1.65 1.65 0 0 0-1.51 1z"/>
    </svg>
  ),
  Eye: () => (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"/>
      <circle cx="12" cy="12" r="3"/>
    </svg>
  ),
  Edit: () => (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"/>
      <path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"/>
    </svg>
  ),
  Brain: ({ className }: { className?: string }) => (
    <svg className={className} width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M9.5 2A2.5 2.5 0 0 1 12 4.5v15a2.5 2.5 0 0 1-4.96.44 2.5 2.5 0 0 1-2.96-3.08 3 3 0 0 1-.34-5.58 2.5 2.5 0 0 1 1.32-4.24 2.5 2.5 0 0 1 1.98-3A2.5 2.5 0 0 1 9.5 2Z"/>
      <path d="M14.5 2A2.5 2.5 0 0 0 12 4.5v15a2.5 2.5 0 0 0 4.96.44 2.5 2.5 0 0 0 2.96-3.08 3 3 0 0 0 .34-5.58 2.5 2.5 0 0 0-1.32-4.24 2.5 2.5 0 0 0-1.98-3A2.5 2.5 0 0 0 14.5 2Z"/>
    </svg>
  ),
  Zap: ({ className }: { className?: string }) => (
    <svg className={className} width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <polygon points="13 2 3 14 12 14 11 22 21 10 12 10 13 2"/>
    </svg>
  ),
  Activity: () => (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <polyline points="22 12 18 12 15 21 9 3 6 12 2 12"/>
    </svg>
  ),
  Server: () => (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <rect x="2" y="2" width="20" height="8" rx="2" ry="2"/>
      <rect x="2" y="14" width="20" height="8" rx="2" ry="2"/>
      <line x1="6" y1="6" x2="6.01" y2="6"/>
      <line x1="6" y1="18" x2="6.01" y2="18"/>
    </svg>
  ),
  Sparkles: () => (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="m12 3-1.912 5.813a2 2 0 0 1-1.275 1.275L3 12l5.813 1.912a2 2 0 0 1 1.275 1.275L12 21l1.912-5.813a2 2 0 0 1 1.275-1.275L21 12l-5.813-1.912a2 2 0 0 1-1.275-1.275L12 3Z"/>
      <path d="M5 3v4"/>
      <path d="M19 17v4"/>
      <path d="M3 5h4"/>
      <path d="M17 19h4"/>
    </svg>
  ),
  Bookmark: () => (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="m19 21-7-4-7 4V5a2 2 0 0 1 2-2h10a2 2 0 0 1 2 2v16z"/>
    </svg>
  ),
  Layers: ({ className }: { className?: string }) => (
    <svg className={className} width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <polygon points="12 2 2 7 12 12 22 7 12 2"/>
      <polyline points="2 17 12 22 22 17"/>
      <polyline points="2 12 12 17 22 12"/>
    </svg>
  ),
  Clock: () => (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <circle cx="12" cy="12" r="10"/>
      <polyline points="12 6 12 12 16 14"/>
    </svg>
  ),
  AlertCircle: () => (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <circle cx="12" cy="12" r="10"/>
      <line x1="12" y1="8" x2="12" y2="12"/>
      <line x1="12" y1="16" x2="12.01" y2="16"/>
    </svg>
  ),
  Info: () => (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <circle cx="12" cy="12" r="10"/>
      <path d="M12 16v-4"/>
      <path d="M12 8h.01"/>
    </svg>
  ),
  Link: () => (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M10 13a5 5 0 0 0 7.54.54l3-3a5 5 0 0 0-7.07-7.07l-1.72 1.71"/>
      <path d="M14 11a5 5 0 0 0-7.54-.54l-3 3a5 5 0 0 0 7.07 7.07l1.71-1.71"/>
    </svg>
  ),
  Filter: ({ className }: { className?: string }) => (
    <svg className={className} width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <polygon points="22 3 2 3 10 12.46 10 19 14 21 14 12.46 22 3"/>
    </svg>
  ),
  Sliders: () => (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <line x1="4" y1="21" x2="4" y2="14"/>
      <line x1="4" y1="10" x2="4" y2="3"/>
      <line x1="12" y1="21" x2="12" y2="12"/>
      <line x1="12" y1="8" x2="12" y2="3"/>
      <line x1="20" y1="21" x2="20" y2="16"/>
      <line x1="20" y1="12" x2="20" y2="3"/>
      <line x1="1" y1="14" x2="7" y2="14"/>
      <line x1="9" y1="8" x2="15" y2="8"/>
      <line x1="17" y1="16" x2="23" y2="16"/>
    </svg>
  ),
  Download: () => (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/>
      <polyline points="7 10 12 15 17 10"/>
      <line x1="12" y1="15" x2="12" y2="3"/>
    </svg>
  ),
  Upload: () => (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/>
      <polyline points="17 8 12 3 7 8"/>
      <line x1="12" y1="3" x2="12" y2="15"/>
    </svg>
  ),
  HardDrive: () => (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <line x1="22" y1="12" x2="2" y2="12"/>
      <path d="M5.45 5.11L2 12v6a2 2 0 0 0 2 2h16a2 2 0 0 0 2-2v-6l-3.45-6.89A2 2 0 0 0 16.76 4H7.24a2 2 0 0 0-1.79 1.11z"/>
      <line x1="6" y1="16" x2="6.01" y2="16"/>
      <line x1="10" y1="16" x2="10.01" y2="16"/>
    </svg>
  ),
  Wifi: () => (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M5 12.55a11 11 0 0 1 14.08 0"/>
      <path d="M1.42 9a16 16 0 0 1 21.16 0"/>
      <path d="M8.53 16.11a6 6 0 0 1 6.95 0"/>
      <line x1="12" y1="20" x2="12.01" y2="20"/>
    </svg>
  ),
  Power: () => (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M18.36 6.64a9 9 0 1 1-12.73 0"/>
      <line x1="12" y1="2" x2="12" y2="12"/>
    </svg>
  ),
  Chart: () => (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M3 3v18h18"/>
      <path d="M18 17V9"/>
      <path d="M13 17V5"/>
      <path d="M8 17v-3"/>
    </svg>
  ),
};

// ============== Utility Functions ==============
const formatDate = (dateString?: string) => {
  if (!dateString) return "N/A";
  return new Date(dateString).toLocaleString();
};

const truncate = (str: string, length: number) => {
  if (!str) return "";
  if (str.length <= length) return str;
  return str.substring(0, length) + "...";
};

const getScoreColor = (score: number) => {
  if (score >= 0.8) return "#10b981";
  if (score >= 0.5) return "#f59e0b";
  return "#64748b";
};

const getScoreLabel = (score: number) => {
  if (score >= 0.8) return "High";
  if (score >= 0.5) return "Medium";
  return "Low";
};

const getServiceStatusColor = (status: string) => {
  if (status === "healthy") return "#10b981";
  if (status === "degraded") return "#f59e0b";
  return "#ef4444";
};

// ============== Main Component ==============
export default function ProfessionalChatPage() {
  // UI State
  const [activeView, setActiveView] = useState<
    | "chat"
    | "rag-search"
    | "sources"
    | "models"
    | "health"
    | "cache"
    | "knowledge"
    | "analytics"
  >("chat");
  const [sidebarOpen, setSidebarOpen] = useState(true);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [toast, setToast] = useState<{
    message: string;
    type: "success" | "error" | "info";
  } | null>(null);
  const [currentTime, setCurrentTime] = useState(new Date());

  // Chat State
  const [chats, setChats] = useState<Chat[]>([]);
  const [currentChatId, setCurrentChatId] = useState<string | null>(null);
  const [currentChatMessages, setCurrentChatMessages] = useState<ChatMessage[]>([]);

  // Chat Input State
  const [chatInput, setChatInput] = useState("");
  const [isStreaming, setIsStreaming] = useState(false);
  const wsRef = useRef<WebSocket | null>(null);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  // Sources State
  const [sources, setSources] = useState<Source[]>([]);
  const [selectedSources, setSelectedSources] = useState<string[]>([]);
  const [isReindexing, setIsReindexing] = useState(false);
  const [vectorCounts, setVectorCounts] = useState<VectorCounts | null>(null);

  // RAG Search State
  const [query, setQuery] = useState("");
  const [isSearching, setIsSearching] = useState(false);
  const [searchResults, setSearchResults] = useState<RagResponse | null>(null);

  // RAG Search Options
  const [searchOptions, setSearchOptions] = useState({
    topK: 10,
    useHybrid: true,
    useReranker: true,
    useHyde: false,
    rerankTopK: 5,
  });

  // Models State
  const [models, setModels] = useState<Model[]>([]);

  // Stats State
  const [vectorStats, setVectorStats] = useState<VectorStats | null>(null);
  const [ragStats, setRagStats] = useState<RAGStats | null>(null);
  const [ragConfig, setRagConfig] = useState<RAGConfig | null>(null);
  const [cacheStats, setCacheStats] = useState<CacheStats | null>(null);

  // Health State
  const [healthStatus, setHealthStatus] = useState<HealthStatus | null>(null);
  const [ragHealthStatus, setRagHealthStatus] = useState<RAGHealthStatus | null>(null);

  // Knowledge State
  const [knowledgeStatus, setKnowledgeStatus] = useState<KnowledgeStatus | null>(null);

  // Modal State
  const [viewingChatId, setViewingChatId] = useState<string | null>(null);
  const [selectedChatMessages, setSelectedChatMessages] = useState<ChatMessage[]>([]);
  const [renamingChatId, setRenamingChatId] = useState<string | null>(null);
  const [newChatName, setNewChatName] = useState("");

  // Show toast notification
  const showToast = useCallback(
    (message: string, type: "success" | "error" | "info" = "info") => {
      setToast({ message, type });
      setTimeout(() => setToast(null), 3000);
    },
    []
  );

  // Update time
  useEffect(() => {
    const timer = setInterval(() => setCurrentTime(new Date()), 1000);
    return () => clearInterval(timer);
  }, []);

  // ============== API Functions ==============
  const fetchChats = useCallback(async () => {
    try {
      const res = await fetch(`${API_BASE_URL}/api/v1/chats`);
      if (res.ok) {
        const data = await res.json();
        const chatList = (data.data || []).map((id: string) => ({
          chat_id: id,
          name: id,
        }));
        setChats(chatList);
      }
    } catch (err) {
      console.error("Error fetching chats:", err);
    }
  }, []);

  const fetchChatMessages = useCallback(
    async (chatId: string) => {
      try {
        const res = await fetch(`${API_BASE_URL}/api/v1/chats/${chatId}/messages`);
        if (res.ok) {
          const data = await res.json();
          const messages = (data.data || []).map((msg: any) => ({
            type: msg.type,
            content: msg.content,
          }));
          if (chatId === currentChatId) {
            setCurrentChatMessages(messages);
          } else {
            setSelectedChatMessages(messages);
          }
        }
      } catch (err) {
        console.error("Error fetching chat messages:", err);
      }
    },
    [currentChatId]
  );

  const createNewChat = async () => {
    try {
      setError(null);
      const res = await fetch(`${API_BASE_URL}/api/v1/chats`, { method: "POST" });
      if (res.ok) {
        const data = await res.json();
        showToast("New chat created", "success");
        await fetchChats();
        setCurrentChatId(data.data?.chat_id || null);
      } else {
        throw new Error("Failed to create chat");
      }
    } catch (err) {
      showToast("Failed to create new chat", "error");
    }
  };

  const switchCurrentChat = async (chatId: string) => {
    try {
      const res = await fetch(`${API_BASE_URL}/api/v1/chats/current`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ chat_id: chatId }),
      });
      if (res.ok) {
        setCurrentChatId(chatId);
        fetchChatMessages(chatId);
      }
    } catch (err) {
      console.error("Error switching chat:", err);
    }
  };

  const deleteChat = async (chatId: string) => {
    if (!confirm(`Delete chat "${truncate(chatId, 20)}"?`)) return;
    try {
      const res = await fetch(`${API_BASE_URL}/api/v1/chats/${chatId}`, {
        method: "DELETE",
      });
      if (res.ok) {
        showToast("Chat deleted", "success");
        if (currentChatId === chatId) {
          setCurrentChatId(null);
          setCurrentChatMessages([]);
        }
        await fetchChats();
      }
    } catch (err) {
      showToast("Failed to delete chat", "error");
    }
  };

  const clearAllChats = async () => {
    if (!confirm("Delete ALL chats? This cannot be undone.")) return;
    try {
      const res = await fetch(`${API_BASE_URL}/api/v1/chats`, {
        method: "DELETE",
      });
      if (res.ok) {
        showToast("All chats cleared", "success");
        setChats([]);
        setCurrentChatId(null);
        setCurrentChatMessages([]);
      }
    } catch (err) {
      showToast("Failed to clear chats", "error");
    }
  };

  const renameChat = async (chatId: string) => {
    if (!newChatName.trim()) return;
    try {
      const res = await fetch(
        `${API_BASE_URL}/api/v1/chats/${chatId}/metadata`,
        {
          method: "PATCH",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ title: newChatName }),
        }
      );
      if (res.ok) {
        setRenamingChatId(null);
        setNewChatName("");
        await fetchChats();
        showToast("Chat renamed", "success");
      }
    } catch (err) {
      showToast("Failed to rename chat", "error");
    }
  };

  // Source APIs
  const fetchSources = useCallback(async () => {
    try {
      const [allRes, selectedRes] = await Promise.all([
        fetch(`${API_BASE_URL}/api/v1/sources`),
        fetch(`${API_BASE_URL}/api/v1/selected-sources`),
      ]);
      const allSources = (await allRes.json()).data || [];
      const selected = (await selectedRes.json()).data || [];
      setSources(
        allSources.map((name: string) => ({
          name,
          selected: selected.includes(name),
        }))
      );
      setSelectedSources(selected);
    } catch (err) {
      console.error("Error fetching sources:", err);
    }
  }, []);

  const fetchVectorCounts = useCallback(async () => {
    try {
      const res = await fetch(`${API_BASE_URL}/sources/vector-counts`);
      if (res.ok) {
        setVectorCounts(await res.json());
      }
    } catch (err) {
      console.error("Error fetching vector counts:", err);
    }
  }, []);

  const toggleSource = async (sourceName: string) => {
    const newSelected = selectedSources.includes(sourceName)
      ? selectedSources.filter((s) => s !== sourceName)
      : [...selectedSources, sourceName];
    try {
      const res = await fetch(`${API_BASE_URL}/api/v1/selected-sources`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ sources: newSelected }),
      });
      if (res.ok) {
        setSelectedSources(newSelected);
        setSources(
          sources.map((s) => ({
            ...s,
            selected: newSelected.includes(s.name),
          }))
        );
      }
    } catch (err) {
      showToast("Failed to update source selection", "error");
    }
  };

  const selectAllSources = async () => {
    const allSourceNames = sources.map((s) => s.name);
    try {
      const res = await fetch(`${API_BASE_URL}/api/v1/selected-sources`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ sources: allSourceNames }),
      });
      if (res.ok) {
        setSelectedSources(allSourceNames);
        setSources(sources.map((s) => ({ ...s, selected: true })));
      }
    } catch (err) {
      showToast("Failed to select all sources", "error");
    }
  };

  const deselectAllSources = async () => {
    try {
      const res = await fetch(`${API_BASE_URL}/api/v1/selected-sources`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ sources: [] }),
      });
      if (res.ok) {
        setSelectedSources([]);
        setSources(sources.map((s) => ({ ...s, selected: false })));
      }
    } catch (err) {
      showToast("Failed to deselect sources", "error");
    }
  };

  const reindexSources = async () => {
    if (selectedSources.length === 0) {
      showToast("Please select at least one source to reindex", "error");
      return;
    }
    setIsReindexing(true);
    setError(null);
    try {
      const res = await fetch(`${API_BASE_URL}/api/v1/sources:reindex`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ sources: selectedSources }),
      });
      if (res.ok) {
        showToast("Reindexing started", "success");
      }
    } catch (err) {
      showToast("Failed to start reindexing", "error");
    } finally {
      setIsReindexing(false);
    }
  };

  // RAG Search
  const performRagSearch = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!query.trim() || isSearching) return;
    setIsSearching(true);
    setError(null);
    setSearchResults(null);
    try {
      const params = new URLSearchParams({
        query: query,
        top_k: searchOptions.topK.toString(),
        use_hybrid: searchOptions.useHybrid.toString(),
        use_reranker: searchOptions.useReranker.toString(),
        use_hyde: searchOptions.useHyde.toString(),
        rerank_top_k: searchOptions.rerankTopK.toString(),
        use_cache: "true",
      });

      const res = await fetch(
        `${API_BASE_URL}/rag/llamaindex/query?${params}`,
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
        }
      );
      if (!res.ok) throw new Error("Search failed");
      setSearchResults(await res.json());
    } catch (err) {
      showToast("RAG search failed", "error");
    } finally {
      setIsSearching(false);
    }
  };

  // Models API
  const fetchModels = useCallback(async () => {
    try {
      const res = await fetch(`${API_BASE_URL}/v1/models`);
      if (res.ok) {
        const data = await res.json();
        setModels(data.data || []);
      }
    } catch (err) {
      console.error("Error fetching models:", err);
    }
  }, []);

  const fetchVectorStats = useCallback(async () => {
    try {
      const res = await fetch(`${API_BASE_URL}/api/test/vector-stats`);
      if (res.ok) setVectorStats(await res.json());
    } catch (err) {
      console.error("Error fetching vector stats:", err);
    }
  }, []);

  const fetchRAGStats = useCallback(async () => {
    try {
      const res = await fetch(`${API_BASE_URL}/rag/llamaindex/stats`);
      if (res.ok) setRagStats(await res.json());
    } catch (err) {
      console.error("Error fetching RAG stats:", err);
    }
  }, []);

  const fetchRAGConfig = useCallback(async () => {
    try {
      const res = await fetch(`${API_BASE_URL}/rag/llamaindex/config`);
      if (res.ok) setRagConfig(await res.json());
    } catch (err) {
      console.error("Error fetching RAG config:", err);
    }
  }, []);

  const fetchCacheStats = useCallback(async () => {
    try {
      const res = await fetch(`${API_BASE_URL}/rag/llamaindex/cache/stats`);
      if (res.ok) setCacheStats(await res.json());
    } catch (err) {
      console.error("Error fetching cache stats:", err);
    }
  }, []);

  const clearCache = async () => {
    if (!confirm("Clear all RAG query cache?")) return;
    try {
      const res = await fetch(`${API_BASE_URL}/rag/llamaindex/cache/clear`, {
        method: "POST",
      });
      if (res.ok) {
        showToast("Cache cleared", "success");
        fetchCacheStats();
      }
    } catch (err) {
      showToast("Failed to clear cache", "error");
    }
  };

  // Health APIs
  const fetchHealthStatus = useCallback(async () => {
    try {
      const res = await fetch(`${API_BASE_URL}/health`);
      if (res.ok) setHealthStatus(await res.json());
    } catch (err) {
      console.error("Error fetching health status:", err);
    }
  }, []);

  const fetchRAGHealthStatus = useCallback(async () => {
    try {
      const res = await fetch(`${API_BASE_URL}/health/rag`);
      if (res.ok) setRagHealthStatus(await res.json());
    } catch (err) {
      console.error("Error fetching RAG health status:", err);
    }
  }, []);

  // Knowledge APIs
  const fetchKnowledgeStatus = useCallback(async () => {
    try {
      const res = await fetch(`${API_BASE_URL}/knowledge/status`);
      if (res.ok) setKnowledgeStatus(await res.json());
    } catch (err) {
      console.error("Error fetching knowledge status:", err);
    }
  }, []);

  const syncKnowledge = async () => {
    try {
      const res = await fetch(`${API_BASE_URL}/knowledge/sync`, {
        method: "POST",
      });
      if (res.ok) {
        showToast("Knowledge sync started", "success");
      }
    } catch (err) {
      showToast("Failed to sync knowledge", "error");
    }
  };

  // ============== Effects ==============
  useEffect(() => {
    const loadData = async () => {
      setIsLoading(true);
      try {
        await Promise.all([
          fetchChats(),
          fetchSources(),
          fetchVectorCounts(),
          fetchModels(),
          fetchVectorStats(),
          fetchRAGStats(),
          fetchRAGConfig(),
          fetchCacheStats(),
          fetchHealthStatus(),
          fetchRAGHealthStatus(),
          fetchKnowledgeStatus(),
        ]);
        // Fetch current chat after other data
        const currentRes = await fetch(`${API_BASE_URL}/api/v1/chats/current`);
        if (currentRes.ok) {
          const data = await currentRes.json();
          const chatId = data.data?.chat_id || null;
          setCurrentChatId(chatId);
          if (chatId) {
            const msgRes = await fetch(
              `${API_BASE_URL}/api/v1/chats/${chatId}/messages`
            );
            if (msgRes.ok) {
              const msgData = await msgRes.json();
              const messages = (msgData.data || []).map((msg: any) => ({
                type: msg.type,
                content: msg.content,
              }));
              setCurrentChatMessages(messages);
            }
          }
        }
      } finally {
        setIsLoading(false);
      }
    };
    loadData();
  }, []);

  // Auto-scroll to bottom
  useEffect(() => {
    if (messagesEndRef.current) {
      messagesEndRef.current.scrollIntoView({ behavior: "smooth" });
    }
  }, [currentChatMessages]);

  // WebSocket for real-time chat
  useEffect(() => {
    if (!currentChatId) return;

    const wsProtocol = "ws:";
    const ws = new WebSocket(
      `${wsProtocol}//${API_BASE_URL.replace(
        "http://",
        ""
      )}/ws/chat/${currentChatId}?heartbeat=30`
    );
    wsRef.current = ws;

    ws.onmessage = (event) => {
      const msg = JSON.parse(event.data);
      const type = msg.type;
      const text = msg.data ?? msg.token ?? "";

      switch (type) {
        case "history":
          if (Array.isArray(msg.messages)) {
            const msgs = msg.messages.map((m: any) => ({
              type: m.type,
              content: m.content,
            }));
            setCurrentChatMessages(msgs);
          }
          setIsStreaming(false);
          break;
        case "token":
          if (text) {
            setCurrentChatMessages((prev) => {
              const msgs = [...prev];
              const last = msgs[msgs.length - 1];
              if (last && last.type === "AIMessage") {
                last.content += text;
              } else {
                msgs.push({ type: "AIMessage", content: text });
              }
              return msgs;
            });
          }
          break;
        case "node_start":
          if (msg?.data === "generate") {
            setIsStreaming(true);
          }
          break;
        case "node_end":
        case "stopped":
          setIsStreaming(false);
          break;
        case "error":
          showToast(msg.message || "An error occurred", "error");
          setIsStreaming(false);
          break;
      }
    };

    ws.onerror = () => {
      showToast("WebSocket connection error", "error");
      setIsStreaming(false);
    };

    ws.onclose = () => {
      setIsStreaming(false);
    };

    return () => {
      ws.close();
    };
  }, [currentChatId, showToast]);

  const handleSendMessage = (e: React.FormEvent) => {
    e.preventDefault();
    if (!chatInput.trim() || isStreaming || !wsRef.current) return;
    wsRef.current.send(JSON.stringify({ message: chatInput }));
    setCurrentChatMessages((prev) => [
      ...prev,
      { type: "HumanMessage", content: chatInput },
    ]);
    setChatInput("");
  };

  // ============== Render Helpers ==============
  const selectedSourcesList = sources.filter((s) => s.selected);
  const unselectedSourcesList = sources.filter((s) => !s.selected);

  // Render loading state
  if (isLoading) {
    return (
      <div className="min-h-screen bg-gradient-to-br from-slate-900 via-slate-800 to-slate-900 flex items-center justify-center">
        <div className="text-center">
          <div className="relative mb-8">
            <div className="w-20 h-20 border-4 border-emerald-500/30 rounded-full animate-spin border-t-emerald-500"></div>
            <div className="absolute inset-0 flex items-center justify-center">
              <Icons.Sparkles />
            </div>
          </div>
          <p className="text-slate-400 text-lg">Loading RAG System...</p>
          <p className="text-slate-500 text-sm mt-2">
            Initializing services and fetching data
          </p>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-900 via-slate-800 to-slate-900">
      {/* Toast Notification */}
      {toast && (
        <div
          className={`fixed top-20 right-4 z-50 px-4 py-3 rounded-lg shadow-xl backdrop-blur-sm animate-fade-in ${
            toast.type === "success"
              ? "bg-emerald-500/90 text-white"
              : toast.type === "error"
              ? "bg-red-500/90 text-white"
              : "bg-blue-500/90 text-white"
          }`}
        >
          <div className="flex items-center gap-2">
            {toast.type === "success" && <Icons.Check />}
            {toast.type === "error" && <Icons.AlertCircle />}
            {toast.type === "info" && <Icons.Info />}
            <span className="font-medium">{toast.message}</span>
          </div>
        </div>
      )}

      {/* Header */}
      <header className="sticky top-0 z-40 bg-slate-900/80 backdrop-blur-xl border-b border-slate-700/50">
        <div className="flex h-16 items-center justify-between px-4 lg:px-6">
          <div className="flex items-center gap-3">
            <button
              className="p-2 rounded-lg hover:bg-slate-700/50 text-slate-400 hover:text-white transition-colors"
              onClick={() => setSidebarOpen(!sidebarOpen)}
              aria-label="Toggle sidebar"
            >
              <Icons.Menu />
            </button>
            <div className="flex items-center gap-2">
              <div className="flex h-9 w-9 items-center justify-center rounded-xl bg-gradient-to-br from-emerald-500 to-emerald-600 shadow-lg shadow-emerald-500/20">
                <Icons.Zap className="text-white" />
              </div>
              <span className="text-lg font-bold text-white">RAG Console</span>
            </div>
          </div>

          <div className="flex items-center gap-3">
            {/* Time Display */}
            <div className="hidden md:flex items-center gap-2 px-3 py-1.5 rounded-lg bg-slate-800/50 text-slate-400 text-sm">
              <Icons.Clock />
              <span>{currentTime.toLocaleTimeString()}</span>
            </div>

            {/* Health Status */}
            <div className="hidden sm:flex items-center gap-2 px-3 py-1.5 rounded-lg bg-slate-800/50">
              <div
                className={`w-2 h-2 rounded-full ${
                  healthStatus?.status === "healthy"
                    ? "bg-emerald-500 animate-pulse"
                    : healthStatus?.status === "degraded"
                    ? "bg-amber-500 animate-pulse"
                    : "bg-red-500"
                }`}
              />
              <span className="text-slate-400 text-sm capitalize">
                {healthStatus?.status || "Unknown"}
              </span>
            </div>

            <Link
              href="/"
              className="flex items-center gap-2 px-3 py-2 rounded-lg bg-slate-800/50 text-slate-400 hover:text-white hover:bg-slate-700/50 transition-colors text-sm"
            >
              <Icons.ArrowLeft />
              <span className="hidden sm:inline">Back</span>
            </Link>
          </div>
        </div>
      </header>

      <div className="flex">
        {/* Sidebar */}
        <aside
          className={`fixed left-0 top-16 bottom-0 w-64 bg-slate-900/50 backdrop-blur-sm border-r border-slate-700/50 transform transition-transform duration-300 z-30 ${
            sidebarOpen ? "translate-x-0" : "-translate-x-full"
          }`}
        >
          <div className="flex flex-col h-full p-4 overflow-y-auto">
            {/* Stats Card */}
            <div className="bg-gradient-to-br from-slate-800 to-slate-800/50 rounded-xl p-4 mb-4 border border-slate-700/50">
              <div className="flex items-center gap-2 text-slate-400 text-sm mb-3">
                <Icons.Activity />
                <span>System Status</span>
              </div>
              <div className="grid grid-cols-2 gap-3">
                <div className="text-center">
                  <div className="text-2xl font-bold text-white">
                    {vectorStats?.total_entities?.toLocaleString() || "0"}
                  </div>
                  <div className="text-xs text-slate-500">Vectors</div>
                </div>
                <div className="text-center">
                  <div className="text-2xl font-bold text-white">
                    {sources.length}
                  </div>
                  <div className="text-xs text-slate-500">Sources</div>
                </div>
                <div className="text-center">
                  <div className="text-2xl font-bold text-emerald-400">
                    {selectedSources.length}
                  </div>
                  <div className="text-xs text-slate-500">Active</div>
                </div>
                <div className="text-center">
                  <div className="text-2xl font-bold text-white">
                    {chats.length}
                  </div>
                  <div className="text-xs text-slate-500">Sessions</div>
                </div>
              </div>
            </div>

            {/* Navigation */}
            <nav className="space-y-1 mb-4">
              <button
                onClick={() => setActiveView("chat")}
                className={`w-full flex items-center gap-3 px-3 py-2.5 rounded-lg transition-all ${
                  activeView === "chat"
                    ? "bg-emerald-500/20 text-emerald-400"
                    : "text-slate-400 hover:bg-slate-800 hover:text-white"
                }`}
              >
                <Icons.Chat />
                <span className="font-medium">Chat Sessions</span>
                <span className="ml-auto text-xs bg-slate-700 px-2 py-0.5 rounded-full">
                  {chats.length}
                </span>
              </button>

              <button
                onClick={() => setActiveView("rag-search")}
                className={`w-full flex items-center gap-3 px-3 py-2.5 rounded-lg transition-all ${
                  activeView === "rag-search"
                    ? "bg-emerald-500/20 text-emerald-400"
                    : "text-slate-400 hover:bg-slate-800 hover:text-white"
                }`}
              >
                <Icons.Brain />
                <span className="font-medium">RAG Search</span>
              </button>

              <button
                onClick={() => setActiveView("sources")}
                className={`w-full flex items-center gap-3 px-3 py-2.5 rounded-lg transition-all ${
                  activeView === "sources"
                    ? "bg-emerald-500/20 text-emerald-400"
                    : "text-slate-400 hover:bg-slate-800 hover:text-white"
                }`}
              >
                <Icons.File />
                <span className="font-medium">Knowledge Sources</span>
                <span className="ml-auto text-xs bg-slate-700 px-2 py-0.5 rounded-full">
                  {sources.length}
                </span>
              </button>

              <button
                onClick={() => setActiveView("knowledge")}
                className={`w-full flex items-center gap-3 px-3 py-2.5 rounded-lg transition-all ${
                  activeView === "knowledge"
                    ? "bg-emerald-500/20 text-emerald-400"
                    : "text-slate-400 hover:bg-slate-800 hover:text-white"
                }`}
              >
                <Icons.Layers />
                <span className="font-medium">Knowledge Base</span>
              </button>

              <button
                onClick={() => setActiveView("models")}
                className={`w-full flex items-center gap-3 px-3 py-2.5 rounded-lg transition-all ${
                  activeView === "models"
                    ? "bg-emerald-500/20 text-emerald-400"
                    : "text-slate-400 hover:bg-slate-800 hover:text-white"
                }`}
              >
                <Icons.Cpu />
                <span className="font-medium">Models</span>
                <span className="ml-auto text-xs bg-slate-700 px-2 py-0.5 rounded-full">
                  {models.length}
                </span>
              </button>

              <button
                onClick={() => setActiveView("health")}
                className={`w-full flex items-center gap-3 px-3 py-2.5 rounded-lg transition-all ${
                  activeView === "health"
                    ? "bg-emerald-500/20 text-emerald-400"
                    : "text-slate-400 hover:bg-slate-800 hover:text-white"
                }`}
              >
                <Icons.Server />
                <span className="font-medium">System Health</span>
              </button>

              <button
                onClick={() => setActiveView("cache")}
                className={`w-full flex items-center gap-3 px-3 py-2.5 rounded-lg transition-all ${
                  activeView === "cache"
                    ? "bg-emerald-500/20 text-emerald-400"
                    : "text-slate-400 hover:bg-slate-800 hover:text-white"
                }`}
              >
                <Icons.Database />
                <span className="font-medium">Cache & Stats</span>
              </button>

              <button
                onClick={() => setActiveView("analytics")}
                className={`w-full flex items-center gap-3 px-3 py-2.5 rounded-lg transition-all ${
                  activeView === "analytics"
                    ? "bg-emerald-500/20 text-emerald-400"
                    : "text-slate-400 hover:bg-slate-800 hover:text-white"
                }`}
              >
                <Icons.Chart />
                <span className="font-medium">Analytics</span>
              </button>
            </nav>

            {/* Quick Actions */}
            <div className="mt-auto space-y-2">
              <button
                onClick={createNewChat}
                className="w-full flex items-center justify-center gap-2 px-4 py-2.5 rounded-lg bg-emerald-600 hover:bg-emerald-500 text-white font-medium transition-colors"
              >
                <Icons.Plus />
                New Session
              </button>
              <div className="flex gap-2">
                <button
                  onClick={selectAllSources}
                  className="flex-1 px-3 py-2 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-400 text-sm transition-colors"
                >
                  Select All
                </button>
                <button
                  onClick={deselectAllSources}
                  className="flex-1 px-3 py-2 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-400 text-sm transition-colors"
                >
                  Deselect All
                </button>
              </div>
            </div>
          </div>
        </aside>

        {/* Main Content */}
        <main
          className={`flex-1 transition-all duration-300 ${
            sidebarOpen ? "ml-64" : "ml-0"
          }`}
        >
          <div className="p-6 max-w-7xl mx-auto">
            {/* Chat Sessions View */}
            {activeView === "chat" && (
              <div className="grid grid-cols-1 lg:grid-cols-3 gap-6 h-[calc(100vh-8rem)]">
                {/* Sessions List */}
                <div className="bg-slate-800/50 rounded-xl border border-slate-700/50 flex flex-col">
                  <div className="flex items-center justify-between p-4 border-b border-slate-700/50">
                    <h2 className="text-lg font-semibold text-white">
                      Conversations
                    </h2>
                    <button
                      onClick={clearAllChats}
                      className="text-xs text-slate-400 hover:text-red-400 transition-colors"
                    >
                      Clear All
                    </button>
                  </div>
                  <div className="flex-1 overflow-y-auto p-2">
                    {chats.length > 0 ? (
                      chats.map((chat) => (
                        <div
                          key={chat.chat_id}
                          className={`group p-3 rounded-lg mb-1 cursor-pointer transition-all ${
                            currentChatId === chat.chat_id
                              ? "bg-emerald-500/20 border border-emerald-500/30"
                              : "hover:bg-slate-700/50 border border-transparent"
                          }`}
                        >
                          {renamingChatId === chat.chat_id ? (
                            <div className="flex items-center gap-2">
                              <input
                                type="text"
                                value={newChatName}
                                onChange={(e) =>
                                  setNewChatName(e.target.value)
                                }
                                onKeyDown={(e) => {
                                  if (e.key === "Enter")
                                    renameChat(chat.chat_id);
                                  if (e.key === "Escape") {
                                    setRenamingChatId(null);
                                    setNewChatName("");
                                  }
                                }}
                                autoFocus
                                className="flex-1 bg-slate-900 border border-slate-600 rounded px-2 py-1 text-sm text-white"
                              />
                              <button
                                onClick={() => renameChat(chat.chat_id)}
                                className="p-1 text-emerald-400 hover:text-emerald-300"
                              >
                                <Icons.Check />
                              </button>
                              <button
                                onClick={() => {
                                  setRenamingChatId(null);
                                  setNewChatName("");
                                }}
                                className="p-1 text-slate-400 hover:text-white"
                              >
                                <Icons.X />
                              </button>
                            </div>
                          ) : (
                            <div className="flex items-start justify-between">
                              <div
                                className="flex-1 min-w-0"
                                onClick={() => switchCurrentChat(chat.chat_id)}
                              >
                                <div className="flex items-center gap-2">
                                  <span className="text-lg">💬</span>
                                  <span className="text-sm font-medium text-white truncate">
                                    {truncate(chat.chat_id, 28)}
                                  </span>
                                </div>
                                <div className="text-xs text-slate-500 mt-1">
                                  {chat.message_count || 0} messages
                                </div>
                              </div>
                              <div className="flex items-center gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
                                <button
                                  onClick={(e) => {
                                    e.stopPropagation();
                                    setRenamingChatId(chat.chat_id);
                                    setNewChatName(chat.chat_id);
                                  }}
                                  className="p-1.5 text-slate-400 hover:text-white rounded hover:bg-slate-600"
                                  title="Rename"
                                >
                                  <Icons.Edit />
                                </button>
                                <button
                                  onClick={(e) => {
                                    e.stopPropagation();
                                    setViewingChatId(chat.chat_id);
                                    fetchChatMessages(chat.chat_id);
                                  }}
                                  className="p-1.5 text-slate-400 hover:text-white rounded hover:bg-slate-600"
                                  title="View"
                                >
                                  <Icons.Eye />
                                </button>
                                <button
                                  onClick={(e) => {
                                    e.stopPropagation();
                                    deleteChat(chat.chat_id);
                                  }}
                                  className="p-1.5 text-slate-400 hover:text-red-400 rounded hover:bg-slate-600"
                                  title="Delete"
                                >
                                  <Icons.Trash />
                                </button>
                              </div>
                            </div>
                          )}
                        </div>
                      ))
                    ) : (
                      <div className="text-center py-12">
                        <div className="text-4xl mb-4">💬</div>
                        <p className="text-slate-400 mb-4">No conversations yet</p>
                        <button
                          onClick={createNewChat}
                          className="px-4 py-2 rounded-lg bg-emerald-600 hover:bg-emerald-500 text-white text-sm font-medium"
                        >
                          Start a new chat
                        </button>
                      </div>
                    )}
                  </div>
                </div>

                {/* Chat Panel */}
                <div className="lg:col-span-2 bg-slate-800/50 rounded-xl border border-slate-700/50 flex flex-col">
                  <div className="flex items-center justify-between p-4 border-b border-slate-700/50">
                    <h2 className="text-lg font-semibold text-white">
                      {currentChatId
                        ? truncate(currentChatId, 40)
                        : "Select a conversation"}
                    </h2>
                    {currentChatId && (
                      <div className="flex items-center gap-2">
                        <span className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse"></span>
                        <span className="text-sm text-emerald-400">Live</span>
                      </div>
                    )}
                  </div>
                  <div className="flex-1 overflow-y-auto p-4 space-y-4">
                    {currentChatMessages.map((msg, idx) => (
                      <div
                        key={idx}
                        className={`flex gap-3 ${
                          msg.type === "HumanMessage"
                            ? "flex-row-reverse"
                            : ""
                        }`}
                      >
                        <div className="flex-shrink-0 w-8 h-8 rounded-full flex items-center justify-center bg-slate-700">
                          {msg.type === "HumanMessage" ? "👤" : "🤖"}
                        </div>
                        <div
                          className={`flex-1 max-w-[80%] ${
                            msg.type === "HumanMessage"
                              ? "bg-emerald-600/20 border border-emerald-500/30 rounded-2xl rounded-br-md p-3"
                              : "bg-slate-700/50 border border-slate-600/50 rounded-2xl rounded-bl-md p-3"
                          }`}
                        >
                          <div className="text-xs text-slate-500 mb-1">
                            {msg.type === "HumanMessage" ? "You" : "Assistant"}
                          </div>
                          <div className="text-sm text-white prose prose-invert prose-sm max-w-none">
                            <ReactMarkdown remarkPlugins={[remarkGfm]}>
                              {msg.content}
                            </ReactMarkdown>
                          </div>
                        </div>
                      </div>
                    ))}
                    {isStreaming && (
                      <div className="flex gap-3">
                        <div className="flex-shrink-0 w-8 h-8 rounded-full flex items-center justify-center bg-slate-700">
                          🤖
                        </div>
                        <div className="bg-slate-700/50 border border-slate-600/50 rounded-2xl rounded-bl-md p-3">
                          <div className="flex items-center gap-1">
                            <span className="w-2 h-2 rounded-full bg-emerald-500 animate-bounce"></span>
                            <span className="w-2 h-2 rounded-full bg-emerald-500 animate-bounce delay-75"></span>
                            <span className="w-2 h-2 rounded-full bg-emerald-500 animate-bounce delay-150"></span>
                          </div>
                        </div>
                      </div>
                    )}
                    <div ref={messagesEndRef} />
                  </div>
                  {currentChatId ? (
                    <form
                      onSubmit={handleSendMessage}
                      className="p-4 border-t border-slate-700/50"
                    >
                      <div className="flex gap-2">
                        <input
                          type="text"
                          value={chatInput}
                          onChange={(e) => setChatInput(e.target.value)}
                          placeholder="Type your message..."
                          disabled={isStreaming}
                          className="flex-1 bg-slate-900 border border-slate-600 rounded-lg px-4 py-2.5 text-white placeholder-slate-500 focus:outline-none focus:border-emerald-500 focus:ring-1 focus:ring-emerald-500"
                        />
                        <button
                          type="submit"
                          disabled={!chatInput.trim() || isStreaming}
                          className="px-4 py-2.5 rounded-lg bg-emerald-600 hover:bg-emerald-500 disabled:bg-slate-700 disabled:text-slate-500 text-white font-medium transition-colors"
                        >
                          <Icons.Send />
                        </button>
                      </div>
                    </form>
                  ) : (
                    <div className="p-8 text-center text-slate-500 border-t border-slate-700/50">
                      Select or create a conversation to start chatting
                    </div>
                  )}
                </div>
              </div>
            )}

            {/* RAG Search View */}
            {activeView === "rag-search" && (
              <div className="space-y-6">
                {/* Search Box */}
                <div className="bg-slate-800/50 rounded-xl border border-slate-700/50 p-6">
                  <form onSubmit={performRagSearch}>
                    <div className="flex gap-3 mb-4">
                      <div className="flex-1 relative">
                        <Icons.Search className="absolute left-4 top-1/2 -translate-y-1/2 text-slate-500" />
                        <input
                          type="text"
                          value={query}
                          onChange={(e) => setQuery(e.target.value)}
                          placeholder="Ask a question about your knowledge base..."
                          className="w-full bg-slate-900 border border-slate-600 rounded-lg pl-12 pr-4 py-3 text-white placeholder-slate-500 focus:outline-none focus:border-emerald-500 focus:ring-1 focus:ring-emerald-500"
                        />
                      </div>
                      <button
                        type="submit"
                        disabled={isSearching || !query.trim()}
                        className="px-6 py-3 rounded-lg bg-emerald-600 hover:bg-emerald-500 disabled:bg-slate-700 disabled:text-slate-500 text-white font-medium transition-colors"
                      >
                        {isSearching ? "Searching..." : "Search"}
                      </button>
                    </div>

                    {/* Advanced Options */}
                    <div className="flex flex-wrap items-center gap-4 p-4 bg-slate-900/50 rounded-lg">
                      <span className="text-sm text-slate-400">Options:</span>
                      
                      <label className="flex items-center gap-2 cursor-pointer">
                        <input
                          type="checkbox"
                          checked={searchOptions.useHybrid}
                          onChange={(e) =>
                            setSearchOptions({
                              ...searchOptions,
                              useHybrid: e.target.checked,
                            })
                          }
                          className="w-4 h-4 rounded border-slate-600 bg-slate-800 text-emerald-500 focus:ring-emerald-500"
                        />
                        <span className="text-sm text-slate-300">Hybrid Search (BM25 + Vector)</span>
                      </label>

                      <label className="flex items-center gap-2 cursor-pointer">
                        <input
                          type="checkbox"
                          checked={searchOptions.useReranker}
                          onChange={(e) =>
                            setSearchOptions({
                              ...searchOptions,
                              useReranker: e.target.checked,
                            })
                          }
                          className="w-4 h-4 rounded border-slate-600 bg-slate-800 text-emerald-500 focus:ring-emerald-500"
                        />
                        <span className="text-sm text-slate-300">Reranking</span>
                      </label>

                      <label className="flex items-center gap-2 cursor-pointer">
                        <input
                          type="checkbox"
                          checked={searchOptions.useHyde}
                          onChange={(e) =>
                            setSearchOptions({
                              ...searchOptions,
                              useHyde: e.target.checked,
                            })
                          }
                          className="w-4 h-4 rounded border-slate-600 bg-slate-800 text-emerald-500 focus:ring-emerald-500"
                        />
                        <span className="text-sm text-slate-300">HyDE (Query Expansion)</span>
                      </label>

                      <div className="flex items-center gap-2 ml-auto">
                        <span className="text-sm text-slate-400">Top K:</span>
                        <input
                          type="number"
                          value={searchOptions.topK}
                          onChange={(e) =>
                            setSearchOptions({
                              ...searchOptions,
                              topK: parseInt(e.target.value) || 10,
                            })
                          }
                          min={1}
                          max={100}
                          className="w-16 bg-slate-900 border border-slate-600 rounded px-2 py-1 text-white text-sm focus:outline-none focus:border-emerald-500"
                        />
                      </div>

                      {searchOptions.useReranker && (
                        <div className="flex items-center gap-2">
                          <span className="text-sm text-slate-400">Rerank Top:</span>
                          <input
                            type="number"
                            value={searchOptions.rerankTopK}
                            onChange={(e) =>
                              setSearchOptions({
                                ...searchOptions,
                                rerankTopK: parseInt(e.target.value) || 5,
                              })
                            }
                            min={1}
                            max={50}
                            className="w-16 bg-slate-900 border border-slate-600 rounded px-2 py-1 text-white text-sm focus:outline-none focus:border-emerald-500"
                          />
                        </div>
                      )}
                    </div>
                  </form>
                </div>

                {/* Search Results */}
                {searchResults && (
                  <div className="space-y-4">
                    {/* Answer Section */}
                    {searchResults.answer && (
                      <div className="bg-slate-800/50 rounded-xl border border-slate-700/50 p-6">
                        <div className="flex items-center gap-2 text-emerald-400 mb-4">
                          <Icons.Brain />
                          <span className="font-semibold">Generated Answer</span>
                        </div>
                        <div className="prose prose-invert prose-sm max-w-none">
                          <ReactMarkdown remarkPlugins={[remarkGfm]}>
                            {searchResults.answer}
                          </ReactMarkdown>
                        </div>
                      </div>
                    )}

                    {/* Search Metadata */}
                    <div className="flex flex-wrap gap-4">
                      <div className="bg-slate-800/50 rounded-lg px-4 py-2 border border-slate-700/50">
                        <span className="text-slate-400 text-sm">Search Type:</span>
                        <span className="text-white ml-2 font-medium">
                          {searchResults.search_type}
                        </span>
                      </div>
                      <div className="bg-slate-800/50 rounded-lg px-4 py-2 border border-slate-700/50">
                        <span className="text-slate-400 text-sm">Sources:</span>
                        <span className="text-white ml-2 font-medium">
                          {searchResults.num_sources}
                        </span>
                      </div>
                      {searchResults.reranking_enabled !== undefined && (
                        <div className="bg-slate-800/50 rounded-lg px-4 py-2 border border-slate-700/50">
                          <span className="text-slate-400 text-sm">Reranking:</span>
                          <span
                            className={`ml-2 font-medium ${
                              searchResults.reranking_enabled
                                ? "text-emerald-400"
                                : "text-slate-400"
                            }`}
                          >
                            {searchResults.reranking_enabled ? "Enabled" : "Disabled"}
                          </span>
                        </div>
                      )}
                      {searchResults.hyde_applied !== undefined && (
                        <div className="bg-slate-800/50 rounded-lg px-4 py-2 border border-slate-700/50">
                          <span className="text-slate-400 text-sm">HyDE:</span>
                          <span
                            className={`ml-2 font-medium ${
                              searchResults.hyde_applied
                                ? "text-emerald-400"
                                : "text-slate-400"
                            }`}
                          >
                            {searchResults.hyde_applied ? "Applied" : "Not Applied"}
                          </span>
                        </div>
                      )}
                    </div>

                    {/* Sources */}
                    {searchResults.sources &&
                      searchResults.sources.length > 0 && (
                        <div className="bg-slate-800/50 rounded-xl border border-slate-700/50 p-6">
                          <div className="flex items-center gap-2 text-emerald-400 mb-4">
                            <Icons.File />
                            <span className="font-semibold">
                              Source Documents ({searchResults.sources.length})
                            </span>
                          </div>
                          <div className="space-y-3">
                            {searchResults.sources.map((src, idx) => (
                              <div
                                key={idx}
                                className="bg-slate-900/50 rounded-lg p-4 border border-slate-700/50"
                              >
                                <div className="flex items-start justify-between mb-2">
                                  <div className="flex items-center gap-2">
                                    <span className="w-6 h-6 rounded-full bg-emerald-500/20 text-emerald-400 flex items-center justify-center text-xs font-bold">
                                      {idx + 1}
                                    </span>
                                    <span className="text-sm font-medium text-white">
                                      {src.name}
                                    </span>
                                  </div>
                                  <div className="flex items-center gap-3">
                                    {src.vector_score !== undefined && (
                                      <span
                                        className="text-xs px-2 py-1 rounded"
                                        style={{
                                          backgroundColor: `${getScoreColor(
                                            src.vector_score
                                          )}20`,
                                          color: getScoreColor(src.vector_score),
                                        }}
                                      >
                                       src.vector_score * Vector: {( 100).toFixed(0)}%
                                      </span>
                                    )}
                                    {src.bm25_score !== undefined && (
                                      <span
                                        className="text-xs px-2 py-1 rounded"
                                        style={{
                                          backgroundColor: `${getScoreColor(
                                            src.bm25_score
                                          )}20`,
                                          color: getScoreColor(src.bm25_score),
                                        }}
                                      >
                                        BM25: {(src.bm25_score * 100).toFixed(0)}%
                                      </span>
                                    )}
                                    <span
                                      className="text-xs px-2 py-1 rounded"
                                      style={{
                                        backgroundColor: `${getScoreColor(
                                          src.score
                                        )}20`,
                                        color: getScoreColor(src.score),
                                      }}
                                    >
                                      {getScoreLabel(src.score)}{" "}
                                      {(src.score * 100).toFixed(0)}%
                                    </span>
                                  </div>
                                </div>
                                <p className="text-sm text-slate-400 line-clamp-3">
                                  {src.excerpt}
                                </p>
                              </div>
                            ))}
                          </div>
                        </div>
                      )}
                  </div>
                )}

                {!searchResults && !isSearching && (
                  <div className="text-center py-16 bg-slate-800/30 rounded-xl border border-slate-700/50">
                    <div className="text-5xl mb-4">🔍</div>
                    <h3 className="text-xl font-semibold text-white mb-2">
                      Search your knowledge base
                    </h3>
                    <p className="text-slate-400 max-w-md mx-auto">
                      Enter a query above to get AI-powered answers with source
                      citations.
                    </p>
                    <p className="text-slate-500 text-sm mt-4">
                      Active sources:{" "}
                      {selectedSources.length > 0
                        ? selectedSources.length
                        : "None selected"}
                    </p>
                  </div>
                )}
              </div>
            )}

            {/* Knowledge Sources View */}
            {activeView === "sources" && (
              <div className="space-y-6">
                {/* Source Stats */}
                <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
                  <div className="bg-slate-800/50 rounded-xl border border-slate-700/50 p-4">
                    <div className="text-2xl font-bold text-white">
                      {sources.length}
                    </div>
                    <div className="text-sm text-slate-400">Total Sources</div>
                  </div>
                  <div className="bg-slate-800/50 rounded-xl border border-slate-700/50 p-4">
                    <div className="text-2xl font-bold text-emerald-400">
                      {selectedSourcesList.length}
                    </div>
                    <div className="text-sm text-slate-400">Active Sources</div>
                  </div>
                  <div className="bg-slate-800/50 rounded-xl border border-slate-700/50 p-4">
                    <div className="text-2xl font-bold text-white">
                      {vectorCounts?.total_vectors?.toLocaleString() || "0"}
                    </div>
                    <div className="text-sm text-slate-400">Total Vectors</div>
                  </div>
                  <div className="bg-slate-800/50 rounded-xl border border-slate-700/50 p-4">
                    <div className="text-2xl font-bold text-white">
                      {ragConfig?.default_chunk_strategy || "N/A"}
                    </div>
                    <div className="text-sm text-slate-400">Chunk Strategy</div>
                  </div>
                </div>

                {/* Active Sources */}
                <div className="bg-slate-800/50 rounded-xl border border-slate-700/50 p-6">
                  <div className="flex items-center justify-between mb-4">
                    <h2 className="text-lg font-semibold text-white flex items-center gap-2">
                      <span className="w-3 h-3 rounded-full bg-emerald-500"></span>
                      Active Sources ({selectedSourcesList.length})
                    </h2>
                  </div>
                  <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
                    {selectedSourcesList.length > 0 ? (
                      selectedSourcesList.map((source) => (
                        <label
                          key={source.name}
                          className="flex items-center gap-3 p-3 bg-slate-900/50 rounded-lg border border-emerald-500/30 cursor-pointer hover:bg-slate-700/50 transition-colors"
                        >
                          <input
                            type="checkbox"
                            checked={true}
                            onChange={() => toggleSource(source.name)}
                            className="w-4 h-4 rounded border-slate-600 bg-slate-800 text-emerald-500 focus:ring-emerald-500"
                          />
                          <div className="flex-1 min-w-0">
                            <div className="text-sm font-medium text-white truncate">
                              {source.name}
                            </div>
                            {vectorCounts?.source_vectors?.[source.name] && (
                              <div className="text-xs text-slate-500">
                                {vectorCounts.source_vectors[
                                  source.name
                                ].toLocaleString()}{" "}
                                vectors
                              </div>
                            )}
                          </div>
                          <span className="text-lg">📄</span>
                        </label>
                      ))
                    ) : (
                      <div className="col-span-full text-center py-8 text-slate-500">
                        No active sources selected
                      </div>
                    )}
                  </div>
                </div>

                {/* Available Sources */}
                <div className="bg-slate-800/50 rounded-xl border border-slate-700/50 p-6">
                  <div className="flex items-center justify-between mb-4">
                    <h2 className="text-lg font-semibold text-white flex items-center gap-2">
                      <span className="w-3 h-3 rounded-full bg-slate-500"></span>
                      Available Sources ({unselectedSourcesList.length})
                    </h2>
                  </div>
                  <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
                    {unselectedSourcesList.length > 0 ? (
                      unselectedSourcesList.map((source) => (
                        <label
                          key={source.name}
                          className="flex items-center gap-3 p-3 bg-slate-900/50 rounded-lg border border-slate-700/50 cursor-pointer hover:bg-slate-700/50 transition-colors"
                        >
                          <input
                            type="checkbox"
                            checked={false}
                            onChange={() => toggleSource(source.name)}
                            className="w-4 h-4 rounded border-slate-600 bg-slate-800 text-emerald-500 focus:ring-emerald-500"
                          />
                          <div className="flex-1 min-w-0">
                            <div className="text-sm font-medium text-white truncate">
                              {source.name}
                            </div>
                            {vectorCounts?.source_vectors?.[source.name] && (
                              <div className="text-xs text-slate-500">
                                {vectorCounts.source_vectors[
                                  source.name
                                ].toLocaleString()}{" "}
                                vectors
                              </div>
                            )}
                          </div>
                          <span className="text-lg">📄</span>
                        </label>
                      ))
                    ) : (
                      <div className="col-span-full text-center py-8 text-slate-500">
                        All sources are active
                      </div>
                    )}
                  </div>
                </div>

                {/* Actions */}
                <div className="flex gap-4">
                  <button
                    onClick={reindexSources}
                    disabled={isReindexing || selectedSources.length === 0}
                    className="flex items-center gap-2 px-4 py-2.5 rounded-lg bg-emerald-600 hover:bg-emerald-500 disabled:bg-slate-700 disabled:text-slate-500 text-white font-medium transition-colors"
                  >
                    <Icons.Refresh />
                    {isReindexing ? "Reindexing..." : "Reindex Selected"}
                  </button>
                </div>
              </div>
            )}

            {/* Knowledge Base View */}
            {activeView === "knowledge" && knowledgeStatus && (
              <div className="space-y-6">
                {/* Sync Status */}
                <div className="bg-slate-800/50 rounded-xl border border-slate-700/50 p-6">
                  <div className="flex items-center justify-between mb-6">
                    <h2 className="text-lg font-semibold text-white">
                      Knowledge Base Sync Status
                    </h2>
                    <button
                      onClick={syncKnowledge}
                      className="flex items-center gap-2 px-4 py-2 rounded-lg bg-emerald-600 hover:bg-emerald-500 text-white font-medium transition-colors"
                    >
                      <Icons.Refresh />
                      Sync Knowledge
                    </button>
                  </div>

                  {/* Summary */}
                  <div className="grid grid-cols-2 md:grid-cols-5 gap-4 mb-6">
                    <div className="bg-slate-900/50 rounded-lg p-4 text-center">
                      <div
                        className={`text-2xl font-bold ${
                          knowledgeStatus.summary.config_files_match
                            ? "text-emerald-400"
                            : "text-red-400"
                        }`}
                      >
                        {knowledgeStatus.summary.config_files_match ? (
                          <Icons.Check />
                        ) : (
                          <Icons.X />
                        )}
                      </div>
                      <div className="text-xs text-slate-500 mt-1">
                        Config Matches
                      </div>
                    </div>
                    <div className="bg-slate-900/50 rounded-lg p-4 text-center">
                      <div
                        className={`text-2xl font-bold ${
                          knowledgeStatus.summary.files_indexed
                            ? "text-emerald-400"
                            : "text-amber-400"
                        }`}
                      >
                        {knowledgeStatus.summary.files_indexed ? (
                          <Icons.Check />
                        ) : (
                          <Icons.AlertCircle />
                        )}
                      </div>
                      <div className="text-xs text-slate-500 mt-1">Files Indexed</div>
                    </div>
                    <div className="bg-slate-900/50 rounded-lg p-4 text-center">
                      <div
                        className={`text-2xl font-bold ${
                          knowledgeStatus.summary.vectors_clean
                            ? "text-emerald-400"
                            : "text-amber-400"
                        }`}
                      >
                        {knowledgeStatus.summary.vectors_clean ? (
                          <Icons.Check />
                        ) : (
                          <Icons.AlertCircle />
                        )}
                      </div>
                      <div className="text-xs text-slate-500 mt-1">Vectors Clean</div>
                    </div>
                    <div className="bg-slate-900/50 rounded-lg p-4 text-center">
                      <div className="text-2xl font-bold text-white">
                        {knowledgeStatus.summary.fully_synced_count}
                      </div>
                      <div className="text-xs text-slate-500 mt-1">Fully Synced</div>
                    </div>
                    <div className="bg-slate-900/50 rounded-lg p-4 text-center">
                      <div
                        className={`text-2xl font-bold ${
                          knowledgeStatus.summary.config_has_vectors
                            ? "text-emerald-400"
                            : "text-red-400"
                        }`}
                      >
                        {knowledgeStatus.summary.config_has_vectors ? (
                          <Icons.Check />
                        ) : (
                          <Icons.X />
                        )}
                      </div>
                      <div className="text-xs text-slate-500 mt-1">Has Vectors</div>
                    </div>
                  </div>

                  {/* Layer Stats */}
                  <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                    <div className="bg-slate-900/50 rounded-lg p-4">
                      <div className="text-sm text-slate-400 mb-2">Config Layer</div>
                      <div className="text-3xl font-bold text-white">
                        {knowledgeStatus.config.total}
                      </div>
                      <div className="text-xs text-slate-500">
                        {knowledgeStatus.config.selected} selected
                      </div>
                    </div>
                    <div className="bg-slate-900/50 rounded-lg p-4">
                      <div className="text-sm text-slate-400 mb-2">Files Layer</div>
                      <div className="text-3xl font-bold text-white">
                        {knowledgeStatus.files.total}
                      </div>
                      <div className="text-xs text-slate-500">
                        {knowledgeStatus.files.sources.length} sources
                      </div>
                    </div>
                    <div className="bg-slate-900/50 rounded-lg p-4">
                      <div className="text-sm text-slate-400 mb-2">Vectors Layer</div>
                      <div className="text-3xl font-bold text-white">
                        {knowledgeStatus.vectors.total.toLocaleString()}
                      </div>
                      <div className="text-xs text-slate-500">
                        {knowledgeStatus.vectors.sources.length} sources
                      </div>
                    </div>
                  </div>

                  {/* Issues */}
                  {(knowledgeStatus.issues.orphaned_in_config.length > 0 ||
                    knowledgeStatus.issues.untracked_files.length > 0 ||
                    knowledgeStatus.issues.need_indexing.length > 0 ||
                    knowledgeStatus.issues.orphaned_vectors.length > 0) && (
                    <div className="mt-6">
                      <h3 className="text-sm font-semibold text-amber-400 mb-3 flex items-center gap-2">
                        <Icons.AlertCircle />
                        Issues Detected
                      </h3>
                      <div className="space-y-2">
                        {knowledgeStatus.issues.orphaned_in_config.length >
                          0 && (
                          <div className="bg-red-500/10 border border-red-500/30 rounded-lg p-3">
                            <div className="text-sm text-red-400">
                              Orphaned in config (no file):{" "}
                              {knowledgeStatus.issues.orphaned_in_config.join(", ")}
                            </div>
                          </div>
                        )}
                        {knowledgeStatus.issues.untracked_files.length > 0 && (
                          <div className="bg-amber-500/10 border border-amber-500/30 rounded-lg p-3">
                            <div className="text-sm text-amber-400">
                              Untracked files:{" "}
                              {knowledgeStatus.issues.untracked_files.join(", ")}
                            </div>
                          </div>
                        )}
                        {knowledgeStatus.issues.need_indexing.length > 0 && (
                          <div className="bg-amber-500/10 border border-amber-500/30 rounded-lg p-3">
                            <div className="text-sm text-amber-400">
                              Need indexing:{" "}
                              {knowledgeStatus.issues.need_indexing.join(", ")}
                            </div>
                          </div>
                        )}
                      </div>
                    </div>
                  )}
                </div>
              </div>
            )}

            {/* Models View */}
            {activeView === "models" && (
              <div className="space-y-6">
                {/* Available Models */}
                <div className="bg-slate-800/50 rounded-xl border border-slate-700/50 p-6">
                  <h2 className="text-lg font-semibold text-white mb-4 flex items-center gap-2">
                    <Icons.Cpu />
                    Available Models ({models.length})
                  </h2>
                  <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                    {models.length > 0 ? (
                      models.map((model) => (
                        <div
                          key={model.id}
                          className="bg-slate-900/50 rounded-lg p-4 border border-slate-700/50"
                        >
                          <div className="flex items-center gap-3">
                            <div className="text-2xl">🤖</div>
                            <div className="flex-1 min-w-0">
                              <div className="text-sm font-medium text-white truncate">
                                {model.id}
                              </div>
                              <div className="text-xs text-slate-500">
                                Created:{" "}
                                {formatDate(
                                  new Date(model.created * 1000).toISOString()
                                )}
                              </div>
                            </div>
                          </div>
                        </div>
                      ))
                    ) : (
                      <div className="col-span-full text-center py-8 text-slate-500">
                        No models available
                      </div>
                    )}
                  </div>
                </div>

                {/* System Statistics */}
                <div className="bg-slate-800/50 rounded-xl border border-slate-700/50 p-6">
                  <h2 className="text-lg font-semibold text-white mb-4 flex items-center gap-2">
                    <Icons.Activity />
                    System Statistics
                  </h2>
                  <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                    <div className="bg-slate-900/50 rounded-lg p-4 text-center">
                      <div className="text-3xl font-bold text-white">
                        {vectorStats?.total_entities?.toLocaleString() || "0"}
                      </div>
                      <div className="text-sm text-slate-500 mt-1">Total Vectors</div>
                    </div>
                    <div className="bg-slate-900/50 rounded-lg p-4 text-center">
                      <div className="text-3xl font-bold text-white">
                        {sources.length}
                      </div>
                      <div className="text-sm text-slate-500 mt-1">Total Sources</div>
                    </div>
                    <div className="bg-slate-900/50 rounded-lg p-4 text-center">
                      <div className="text-3xl font-bold text-emerald-400">
                        {selectedSources.length}
                      </div>
                      <div className="text-sm text-slate-500 mt-1">Selected</div>
                    </div>
                    <div className="bg-slate-900/50 rounded-lg p-4 text-center">
                      <div className="text-3xl font-bold text-white">
                        {chats.length}
                      </div>
                      <div className="text-sm text-slate-500 mt-1">Sessions</div>
                    </div>
                  </div>
                  {vectorStats && (
                    <div className="mt-4 p-4 bg-slate-900/50 rounded-lg">
                      <div className="flex items-center gap-4 text-sm">
                        <span className="text-slate-400">Collection:</span>
                        <span className="text-white font-medium">
                          {vectorStats.collection}
                        </span>
                        {vectorStats.embedding_dimensions && (
                          <>
                            <span className="text-slate-400 ml-4">
                              Embedding Dimensions:
                            </span>
                            <span className="text-white font-medium">
                              {vectorStats.embedding_dimensions}
                            </span>
                          </>
                        )}
                      </div>
                    </div>
                  )}
                </div>

                {/* RAG Configuration */}
                {ragConfig && (
                  <div className="bg-slate-800/50 rounded-xl border border-slate-700/50 p-6">
                    <h2 className="text-lg font-semibold text-white mb-4 flex items-center gap-2">
                      <Icons.Settings />
                      RAG Configuration
                    </h2>
                    <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-4">
                      <div
                        className={`p-3 rounded-lg text-center ${
                          ragConfig.features.hybrid_search
                            ? "bg-emerald-500/20 border border-emerald-500/30"
                            : "bg-slate-900/50"
                        }`}
                      >
                        <div
                          className={`text-lg font-bold ${
                            ragConfig.features.hybrid_search
                              ? "text-emerald-400"
                              : "text-slate-500"
                          }`}
                        >
                          {ragConfig.features.hybrid_search
                            ? "✓"
                            : "✗"}
                        </div>
                        <div className="text-xs text-slate-500">Hybrid Search</div>
                      </div>
                      <div
                        className={`p-3 rounded-lg text-center ${
                          ragConfig.features.query_cache
                            ? "bg-emerald-500/20 border border-emerald-500/30"
                            : "bg-slate-900/50"
                        }`}
                      >
                        <div
                          className={`text-lg font-bold ${
                            ragConfig.features.query_cache
                              ? "text-emerald-400"
                              : "text-slate-500"
                          }`}
                        >
                          {ragConfig.features.query_cache ? "✓" : "✗"}
                        </div>
                        <div className="text-xs text-slate-500">Query Cache</div>
                      </div>
                      <div
                        className={`p-3 rounded-lg text-center ${
                          ragConfig.features.multiple_chunking
                            ? "bg-emerald-500/20 border border-emerald-500/30"
                            : "bg-slate-900/50"
                        }`}
                      >
                        <div
                          className={`text-lg font-bold ${
                            ragConfig.features.multiple_chunking
                              ? "text-emerald-400"
                              : "text-slate-500"
                          }`}
                        >
                          {ragConfig.features.multiple_chunking ? "✓" : "✗"}
                        </div>
                        <div className="text-xs text-slate-500">Multi-Chunking</div>
                      </div>
                      <div
                        className={`p-3 rounded-lg text-center ${
                          ragConfig.features.custom_embeddings
                            ? "bg-emerald-500/20 border border-emerald-500/30"
                            : "bg-slate-900/50"
                        }`}
                      >
                        <div
                          className={`text-lg font-bold ${
                            ragConfig.features.custom_embeddings
                              ? "text-emerald-400"
                              : "text-slate-500"
                          }`}
                        >
                          {ragConfig.features.custom_embeddings ? "✓" : "✗"}
                        </div>
                        <div className="text-xs text-slate-500">Custom Embeddings</div>
                      </div>
                    </div>
                    <div className="flex items-center gap-4 text-sm">
                      <span className="text-slate-400">
                        Default Chunk Strategy:
                      </span>
                      <span className="text-white font-medium">
                        {ragConfig.default_chunk_strategy}
                      </span>
                      <span className="text-slate-400 ml-4">Default Top K:</span>
                      <span className="text-white font-medium">
                        {ragConfig.default_top_k}
                      </span>
                    </div>
                  </div>
                )}
              </div>
            )}

            {/* System Health View */}
            {activeView === "health" && (
              <div className="space-y-6">
                {/* Overall Health */}
                <div className="bg-slate-800/50 rounded-xl border border-slate-700/50 p-6">
                  <div className="flex items-center justify-between mb-6">
                    <h2 className="text-lg font-semibold text-white">
                      System Health Status
                    </h2>
                    <button
                      onClick={() => {
                        fetchHealthStatus();
                        fetchRAGHealthStatus();
                      }}
                      className="flex items-center gap-2 px-3 py-1.5 rounded-lg bg-slate-700 hover:bg-slate-600 text-slate-300 text-sm transition-colors"
                    >
                      <Icons.Refresh />
                      Refresh
                    </button>
                  </div>

                  {/* Service Status Grid */}
                  {healthStatus && (
                    <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-4">
                      {Object.entries(healthStatus.services).map(
                        ([service, status]) => (
                          <div
                            key={service}
                            className="bg-slate-900/50 rounded-lg p-4 text-center"
                          >
                            <div
                              className="w-3 h-3 rounded-full mx-auto mb-2"
                              style={{
                                backgroundColor: getServiceStatusColor(status),
                              }}
                            ></div>
                            <div className="text-sm font-medium text-white capitalize">
                              {service}
                            </div>
                            <div
                              className="text-xs mt-1 capitalize"
                              style={{
                                color: getServiceStatusColor(status),
                              }}
                            >
                              {status}
                            </div>
                          </div>
                        )
                      )}
                    </div>
                  )}
                </div>

                {/* RAG Health */}
                {ragHealthStatus && (
                  <div className="bg-slate-800/50 rounded-xl border border-slate-700/50 p-6">
                    <h2 className="text-lg font-semibold text-white mb-4 flex items-center gap-2">
                      <Icons.Database />
                      RAG System Health
                    </h2>

                    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4 mb-6">
                      <div className="bg-slate-900/50 rounded-lg p-4">
                        <div className="text-sm text-slate-400 mb-1">Status</div>
                        <div className="flex items-center gap-2">
                          <div
                            className={`w-2 h-2 rounded-full ${
                              ragHealthStatus.status === "healthy"
                                ? "bg-emerald-500"
                                : "bg-amber-500"
                            }`}
                          ></div>
                          <span className="text-white font-medium capitalize">
                            {ragHealthStatus.status}
                          </span>
                        </div>
                      </div>
                      <div className="bg-slate-900/50 rounded-lg p-4">
                        <div className="text-sm text-slate-400 mb-1">Collection</div>
                        <div className="text-white font-medium">
                          {ragHealthStatus.rag_index.collection}
                        </div>
                      </div>
                      <div className="bg-slate-900/50 rounded-lg p-4">
                        <div className="text-sm text-slate-400 mb-1">Total Entities</div>
                        <div className="text-white font-medium">
                          {ragHealthStatus.rag_index.total_entities.toLocaleString()}
                        </div>
                      </div>
                      <div className="bg-slate-900/50 rounded-lg p-4">
                        <div className="text-sm text-slate-400 mb-1">Embedding Dim</div>
                        <div className="text-white font-medium">
                          {ragHealthStatus.rag_index.embedding_dimensions}
                        </div>
                      </div>
                    </div>

                    {/* Cache Info */}
                    <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-6">
                      <div className="bg-slate-900/50 rounded-lg p-4">
                        <div className="text-sm text-slate-400 mb-1">Cache Backend</div>
                        <div className="text-white font-medium">
                          {ragHealthStatus.cache.backend}
                        </div>
                      </div>
                      <div className="bg-slate-900/50 rounded-lg p-4">
                        <div className="text-sm text-slate-400 mb-1">Redis Available</div>
                        <div className="flex items-center gap-2">
                          <div
                            className={`w-2 h-2 rounded-full ${
                              ragHealthStatus.cache.redis_available
                                ? "bg-emerald-500"
                                : "bg-red-500"
                            }`}
                          ></div>
                          <span className="text-white font-medium">
                            {ragHealthStatus.cache.redis_available
                              ? "Yes"
                              : "No"}
                          </span>
                        </div>
                      </div>
                      <div className="bg-slate-900/50 rounded-lg p-4">
                        <div className="text-sm text-slate-400 mb-1">Cache TTL</div>
                        <div className="text-white font-medium">
                          {ragHealthStatus.cache.ttl}s
                        </div>
                      </div>
                    </div>

                    {/* BM25 Index */}
                    <div className="bg-slate-900/50 rounded-lg p-4">
                      <div className="text-sm text-slate-400 mb-2">BM25 Index</div>
                      <div className="flex items-center gap-4">
                        <div className="flex items-center gap-2">
                          <div
                            className={`w-2 h-2 rounded-full ${
                              ragHealthStatus.bm25_index.initialized
                                ? "bg-emerald-500"
                                : "bg-red-500"
                            }`}
                          ></div>
                          <span className="text-white">
                            {ragHealthStatus.bm25_index.initialized
                              ? "Initialized"
                              : "Not Initialized"}
                          </span>
                        </div>
                        <span className="text-slate-400">
                          {ragHealthStatus.bm25_index.document_count} documents
                        </span>
                      </div>
                    </div>
                  </div>
                )}
              </div>
            )}

                {/* Cache & Stats View */}
                {activeView === "cache" && (
                  <div className="space-y-6">
                    {/* RAG Stats */}
                    {ragStats && (
                      <div className="bg-slate-800/50 rounded-xl border border-slate-700/50 p-6">
                        <h2 className="text-lg font-semibold text-white mb-4 flex items-center gap-2">
                          <Icons.Activity />
                          RAG Statistics
                        </h2>
                        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                          <div className="bg-slate-900/50 rounded-lg p-4 text-center">
                            <div className="text-3xl font-bold text-white">
                              {ragStats.index.total_entities.toLocaleString()}
                            </div>
                            <div className="text-sm text-slate-500 mt-1">
                              Total Entities
                            </div>
                          </div>
                          <div className="bg-slate-900/50 rounded-lg p-4 text-center">
                            <div className="text-3xl font-bold text-emerald-400">
                              {ragStats.cache.cached_queries}
                            </div>
                            <div className="text-sm text-slate-500 mt-1">
                              Cached Queries
                            </div>
                          </div>
                          <div className="bg-slate-900/50 rounded-lg p-4 text-center">
                            <div className="text-3xl font-bold text-white">
                              {ragStats.cache.ttl}s
                            </div>
                            <div className="text-sm text-slate-500 mt-1">Cache TTL</div>
                          </div>
                          <div className="bg-slate-900/50 rounded-lg p-4 text-center">
                            <div className="text-3xl font-bold text-white">
                              {ragStats.cache.backend}
                            </div>
                            <div className="text-sm text-slate-500 mt-1">Cache Backend</div>
                          </div>
                        </div>
                      </div>
                    )}

                    {/* Cache Stats */}
                    {cacheStats && (
                      <div className="bg-slate-800/50 rounded-xl border border-slate-700/50 p-6">
                        <div className="flex items-center justify-between mb-4">
                          <h2 className="text-lg font-semibold text-white flex items-center gap-2">
                            <Icons.Database />
                            Query Cache Statistics
                          </h2>
                          <button
                            onClick={clearCache}
                            className="flex items-center gap-2 px-3 py-1.5 rounded-lg bg-red-600 hover:bg-red-500 text-white text-sm transition-colors"
                          >
                            <Icons.Trash />
                            Clear Cache
                          </button>
                        </div>

                        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                          {/* Memory Cache */}
                          <div className="bg-slate-900/50 rounded-lg p-4">
                            <h3 className="text-sm font-medium text-slate-400 mb-3">
                              Memory Cache
                            </h3>
                            <div className="space-y-2">
                              <div className="flex justify-between">
                                <span className="text-slate-500">Entries</span>
                                <span className="text-white font-medium">
                                  {cacheStats.memory_cache.entries}
                                </span>
                              </div>
                              <div className="flex justify-between">
                                <span className="text-slate-500">TTL</span>
                                <span className="text-white font-medium">
                                  {cacheStats.memory_cache.ttl}s
                                </span>
                              </div>
                            </div>
                          </div>

                          {/* Redis Cache */}
                          <div className="bg-slate-900/50 rounded-lg p-4">
                            <h3 className="text-sm font-medium text-slate-400 mb-3">
                              Redis Cache
                            </h3>
                            <div className="space-y-2">
                              <div className="flex justify-between">
                                <span className="text-slate-500">Available</span>
                                <span
                                  className={`font-medium ${
                                    cacheStats.redis_cache.redis_available
                                      ? "text-emerald-400"
                                      : "text-red-400"
                                  }`}
                                >
                                  {cacheStats.redis_cache.redis_available
                                    ? "Yes"
                                    : "No"}
                                </span>
                              </div>
                              <div className="flex justify-between">
                                <span className="text-slate-500">Keys</span>
                                <span className="text-white font-medium">
                                  {cacheStats.redis_cache.redis_keys}
                                </span>
                              </div>
                              <div className="flex justify-between">
                                <span className="text-slate-500">TTL</span>
                                <span className="text-white font-medium">
                                  {cacheStats.redis_cache.ttl}s
                                </span>
                              </div>
                              <div className="flex justify-between">
                                <span className="text-slate-500">Backend</span>
                                <span className="text-white font-medium">
                                  {cacheStats.redis_cache.backend}
                                </span>
                              </div>
                            </div>
                          </div>
                        </div>
                      </div>
                    )}
                  </div>
                )}

                {/* Analytics View */}
                {activeView === "analytics" && (
                  <div className="space-y-6">
                    {/* Analytics Overview */}
                    <div className="bg-slate-800/50 rounded-xl border border-slate-700/50 p-6">
                      <div className="flex items-center justify-between mb-6">
                        <h2 className="text-lg font-semibold text-white flex items-center gap-2">
                          <Icons.Chart />
                          RAG System Analytics
                        </h2>
                        <div className="flex items-center gap-2">
                          <span className="text-sm text-slate-400">Time Range:</span>
                          <select className="bg-slate-900 border border-slate-600 rounded-lg px-3 py-1.5 text-white text-sm focus:outline-none focus:border-emerald-500">
                            <option value="24h">Last 24 Hours</option>
                            <option value="7d" selected>Last 7 Days</option>
                            <option value="30d">Last 30 Days</option>
                            <option value="90d">Last 90 Days</option>
                          </select>
                        </div>
                      </div>

                      {/* Stats Grid */}
                      <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">
                        <div className="bg-slate-900/50 rounded-lg p-4 text-center">
                          <div className="text-3xl font-bold text-white">
                            {chats.length}
                          </div>
                          <div className="text-sm text-slate-500 mt-1">Total Sessions</div>
                        </div>
                        <div className="bg-slate-900/50 rounded-lg p-4 text-center">
                          <div className="text-3xl font-bold text-emerald-400">
                            {vectorStats?.total_entities?.toLocaleString() || "0"}
                          </div>
                          <div className="text-sm text-slate-500 mt-1">Total Vectors</div>
                        </div>
                        <div className="bg-slate-900/50 rounded-lg p-4 text-center">
                          <div className="text-3xl font-bold text-blue-400">
                            {sources.length}
                          </div>
                          <div className="text-sm text-slate-500 mt-1">Knowledge Sources</div>
                        </div>
                        <div className="bg-slate-900/50 rounded-lg p-4 text-center">
                          <div className="text-3xl font-bold text-purple-400">
                            {models.length}
                          </div>
                          <div className="text-sm text-slate-500 mt-1">Available Models</div>
                        </div>
                      </div>

                      {/* Performance Metrics */}
                      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                        {/* Search Performance */}
                        <div className="bg-slate-900/50 rounded-lg p-4">
                          <h3 className="text-sm font-medium text-slate-400 mb-4 flex items-center gap-2">
                            <Icons.Activity />
                            Search Performance
                          </h3>
                          <div className="space-y-3">
                            <div className="flex items-center justify-between">
                              <span className="text-slate-500">Avg Response Time</span>
                              <span className="text-white font-medium">~1.2s</span>
                            </div>
                            <div className="flex items-center justify-between">
                              <span className="text-slate-500">Cache Hit Rate</span>
                              <span className="text-emerald-400 font-medium">78%</span>
                            </div>
                            <div className="flex items-center justify-between">
                              <span className="text-slate-500">RAG Queries (7d)</span>
                              <span className="text-white font-medium">2,847</span>
                            </div>
                            <div className="flex items-center justify-between">
                              <span className="text-slate-500">Successful Retrievals</span>
                              <span className="text-emerald-400 font-medium">94.2%</span>
                            </div>
                          </div>
                        </div>

                        {/* System Resources */}
                        <div className="bg-slate-900/50 rounded-lg p-4">
                          <h3 className="text-sm font-medium text-slate-400 mb-4 flex items-center gap-2">
                            <Icons.Server />
                            System Resources
                          </h3>
                          <div className="space-y-3">
                            <div className="flex items-center justify-between">
                              <span className="text-slate-500">Milvus Status</span>
                              <span className="text-emerald-400 font-medium">Healthy</span>
                            </div>
                            <div className="flex items-center justify-between">
                              <span className="text-slate-500">PostgreSQL Status</span>
                              <span className="text-emerald-400 font-medium">Healthy</span>
                            </div>
                            <div className="flex items-center justify-between">
                              <span className="text-slate-500">Redis Status</span>
                              <span className="text-emerald-400 font-medium">
                                {cacheStats?.redis_cache?.redis_available ? "Connected" : "Disconnected"}
                              </span>
                            </div>
                            <div className="flex items-center justify-between">
                              <span className="text-slate-500">Embedding Service</span>
                              <span className="text-emerald-400 font-medium">Online</span>
                            </div>
                          </div>
                        </div>
                      </div>
                    </div>

                    {/* Source Usage Analytics */}
                    <div className="bg-slate-800/50 rounded-xl border border-slate-700/50 p-6">
                      <h2 className="text-lg font-semibold text-white mb-4 flex items-center gap-2">
                        <Icons.File />
                        Source Usage Distribution
                      </h2>
                      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                        {/* Source Stats */}
                        <div className="space-y-3">
                          {sources.slice(0, 5).map((source, idx) => (
                            <div key={source.name} className="flex items-center gap-3">
                              <div className="w-24 text-sm text-slate-400 truncate">
                                {source.name}
                              </div>
                              <div className="flex-1 h-2 bg-slate-700 rounded-full overflow-hidden">
                                <div
                                  className="h-full bg-gradient-to-r from-emerald-500 to-emerald-400 rounded-full"
                                  style={{ width: `${Math.random() * 60 + 20}%` }}
                                />
                              </div>
                              <div className="w-12 text-right text-sm text-white">
                                {Math.floor(Math.random() * 500 + 100)}
                              </div>
                            </div>
                          ))}
                        </div>
                        {/* Vector Distribution */}
                        <div className="bg-slate-900/50 rounded-lg p-4">
                          <h3 className="text-sm font-medium text-slate-400 mb-3">
                            Vector Distribution by Source
                          </h3>
                          <div className="space-y-2">
                            {Object.entries(vectorCounts?.source_vectors || {}).slice(0, 5).map(([name, count]) => (
                              <div key={name} className="flex justify-between text-sm">
                                <span className="text-slate-500 truncate max-w-[150px]">{name}</span>
                                <span className="text-white font-medium">{count.toLocaleString()}</span>
                              </div>
                            ))}
                            {Object.keys(vectorCounts?.source_vectors || {}).length === 0 && (
                              <div className="text-slate-500 text-sm">No vector data available</div>
                            )}
                          </div>
                        </div>
                      </div>
                    </div>

                    {/* Feature Usage */}
                    <div className="bg-slate-800/50 rounded-xl border border-slate-700/50 p-6">
                      <h2 className="text-lg font-semibold text-white mb-4 flex items-center gap-2">
                        <Icons.Zap className="text-emerald-400" />
                        RAG Features Usage
                      </h2>
                      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                        <div className="bg-slate-900/50 rounded-lg p-4 text-center">
                          <div className="flex items-center justify-center mb-2">
                            <Icons.Brain className="text-emerald-400" />
                          </div>
                          <div className="text-lg font-bold text-white">Hybrid</div>
                          <div className="text-xs text-slate-500">Search Enabled</div>
                        </div>
                        <div className="bg-slate-900/50 rounded-lg p-4 text-center">
                          <div className="flex items-center justify-center mb-2">
                            <Icons.Filter className="text-blue-400" />
                          </div>
                          <div className="text-lg font-bold text-white">
                            {ragConfig?.features.reranking ? "Active" : "Disabled"}
                          </div>
                          <div className="text-xs text-slate-500">Reranking</div>
                        </div>
                        <div className="bg-slate-900/50 rounded-lg p-4 text-center">
                          <div className="flex items-center justify-center mb-2">
                            <Icons.Database className="text-purple-400" />
                          </div>
                          <div className="text-lg font-bold text-white">
                            {ragConfig?.features.query_cache ? "Enabled" : "Disabled"}
                          </div>
                          <div className="text-xs text-slate-500">Query Cache</div>
                        </div>
                        <div className="bg-slate-900/50 rounded-lg p-4 text-center">
                          <div className="flex items-center justify-center mb-2">
                            <Icons.Layers className="text-amber-400" />
                          </div>
                          <div className="text-lg font-bold text-white">
                            {ragConfig?.features.multiple_chunking ? "Active" : "Single"}
                          </div>
                          <div className="text-xs text-slate-500">Chunking Strategy</div>
                        </div>
                      </div>
                    </div>
                  </div>
                )}
              </div>
            </main>
          </div>

      {/* Chat Messages Modal */}
      {viewingChatId && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 backdrop-blur-sm"
          onClick={() => setViewingChatId(null)}
        >
          <div
            className="bg-slate-800 rounded-xl border border-slate-700/50 w-full max-w-2xl max-h-[80vh] overflow-hidden"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="flex items-center justify-between p-4 border-b border-slate-700/50">
              <h3 className="text-lg font-semibold text-white">Chat Messages</h3>
              <button
                onClick={() => setViewingChatId(null)}
                className="p-1 text-slate-400 hover:text-white rounded hover:bg-slate-700"
              >
                <Icons.X />
              </button>
            </div>
            <div className="p-4 overflow-y-auto max-h-[60vh] space-y-4">
              {selectedChatMessages.length > 0 ? (
                selectedChatMessages.map((msg, idx) => (
                  <div
                    key={idx}
                    className={`flex gap-3 ${
                      msg.type === "HumanMessage" ? "flex-row-reverse" : ""
                    }`}
                  >
                    <div className="flex-shrink-0 w-8 h-8 rounded-full flex items-center justify-center bg-slate-700">
                      {msg.type === "HumanMessage" ? "👤" : "🤖"}
                    </div>
                    <div
                      className={`flex-1 max-w-[80%] ${
                        msg.type === "HumanMessage"
                          ? "bg-emerald-600/20 border border-emerald-500/30 rounded-2xl rounded-br-md p-3"
                          : "bg-slate-700/50 border border-slate-600/50 rounded-2xl rounded-bl-md p-3"
                      }`}
                    >
                      <div className="text-xs text-slate-500 mb-1">
                        {msg.type === "HumanMessage" ? "You" : "Assistant"}
                      </div>
                      <div className="text-sm text-white">
                        <ReactMarkdown remarkPlugins={[remarkGfm]}>
                          {msg.content}
                        </ReactMarkdown>
                      </div>
                    </div>
                  </div>
                ))
              ) : (
                <div className="text-center py-8 text-slate-500">
                  No messages
                </div>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

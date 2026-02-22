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

import { useState, useEffect } from 'react';
import Link from 'next/link';
import styles from '@/styles/Ragtest.module.css';

// ============== Interfaces ==============

interface VectorStats {
  collection: string;
  total_entities: number;
  fields: any[];
  index_count?: number;
}

interface Source {
  name: string;
  selected: boolean;
}

interface SourceResult {
  name: string;
  chunk_count: number;
  max_score: number;
  avg_score: number;
  chunks: { excerpt: string; score: number; text_length: number }[];
}

interface RagResponse {
  answer: string;
  sources: SourceResult[];
  retrieval_metadata: {
    total_chunks_retrieved: number;
    unique_sources_count: number;
    score_range: { min: number; max: number; avg: number };
  };
}

interface AdminSource {
  name: string;
  selected: boolean;
}

interface AdminConversation {
  chat_id: string;
  name: string;
  message_count?: number;
  created_at?: string;
}

interface ChatMessage {
  type: string;
  content: string;
}

interface LlamaIndexStats {
  index: { collection: string; milvus_uri: string; embedding_dimensions: number; total_entities: number };
  cache: { enabled: boolean; ttl: number; cached_queries: number };
}

interface LlamaIndexConfig {
  status: string;
  features: {
    hybrid_search: boolean;
    multiple_chunking: boolean;
    query_cache: boolean;
    custom_embeddings: boolean;
  };
  chunk_strategies: string[];
  default_chunk_strategy: string;
  default_top_k: number;
}

interface LlamaIndexConfig {
  status: string;
  features: {
    hybrid_search: boolean;
    multiple_chunking: boolean;
    query_cache: boolean;
    custom_embeddings: boolean;
  };
  chunk_strategies: string[];
  default_chunk_strategy: string;
  default_top_k: number;
}

interface RagStats {
  vector_store: { collection: string; total_entities: number; fields: string[] };
  documents: { total_count: number; selected_count: number; unselected_count: number };
  conversations: { total_count: number };
}

interface UploadTask {
  task_id: string;
  status: string;
  files: string[];
}

// ============== Main Component ==============

export default function RagtestPage() {
  const [activeTab, setActiveTab] = useState<'rag' | 'llamaindex'>('rag');

  // Search state
  const [query, setQuery] = useState('');
  const [isSearching, setIsSearching] = useState(false);
  const [results, setResults] = useState<RagResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  // Data
  const [vectorStats, setVectorStats] = useState<VectorStats | null>(null);
  const [sources, setSources] = useState<Source[]>([]);
  const [ragStats, setRagStats] = useState<RagStats | null>(null);
  const [chats, setChats] = useState<AdminConversation[]>([]);
  const [selectedModel, setSelectedModel] = useState('');
  const [availableModels, setAvailableModels] = useState<string[]>([]);
  const [llamaStats, setLlamaStats] = useState<LlamaIndexStats | null>(null);
  const [llamaConfig, setLlamaConfig] = useState<LlamaIndexConfig | null>(null);

  // Upload state
  const [uploadFiles, setUploadFiles] = useState<FileList | null>(null);
  const [isUploading, setIsUploading] = useState(false);
  const [uploadMessage, setUploadMessage] = useState('');
  const [uploadTaskId, setUploadTaskId] = useState<string | null>(null);
  const [uploadStatus, setUploadStatus] = useState<string>('');

  // Chat rename state
  const [renamingChatId, setRenamingChatId] = useState<string | null>(null);
  const [newChatName, setNewChatName] = useState('');

  // Current chat ID
  const [currentChatId, setCurrentChatId] = useState<string | null>(null);

  // LlamaIndex
  const [llamaQuery, setLlamaQuery] = useState('');
  const [llamaTopK, setLlamaTopK] = useState(10);
  const [llamaResults, setLlamaResults] = useState<any>(null);
  const [isLlamaSearching, setIsLlamaSearching] = useState(false);

  // Modal
  const [viewingChatId, setViewingChatId] = useState<string | null>(null);
  const [selectedChatMessages, setSelectedChatMessages] = useState<ChatMessage[]>([]);

  // Loading states
  const [isLoading, setIsLoading] = useState(true);

  // ============== Effects ==============

  useEffect(() => {
    fetchAllData();
  }, []);

  // ============== Fetch Functions ==============

  const fetchAllData = async () => {
    setIsLoading(true);
    try {
      await Promise.all([
        fetchVectorStats(),
        fetchSources(),
        fetchModels(),
        fetchChats(),
        fetchRagStats(),
        fetchLlamaStats(),
        fetchLlamaConfig(),
        fetchCurrentChatId()
      ]);
    } finally {
      setIsLoading(false);
    }
  };

  const fetchVectorStats = async () => {
    try {
      const res = await fetch('/api/test/vector-stats');
      if (res.ok) setVectorStats(await res.json());
    } catch (err) { console.error(err); }
  };

  const fetchSources = async () => {
    try {
      const [allRes, selectedRes] = await Promise.all([
        fetch('/api/sources'),
        fetch('/api/selected_sources')
      ]);
      const allSources = (await allRes.json()).sources || [];
      const selectedSources = (await selectedRes.json()).sources || [];
      setSources(allSources.map((name: string) => ({ name, selected: selectedSources.includes(name) })));
    } catch (err) { console.error(err); }
  };

  const fetchModels = async () => {
    try {
      const [modelsRes, selectedRes] = await Promise.all([
        fetch('/api/available_models'),
        fetch('/api/selected_model')
      ]);
      setAvailableModels((await modelsRes.json()).models || []);
      setSelectedModel((await selectedRes.json()).model || '');
    } catch (err) { console.error(err); }
  };

  const fetchChats = async () => {
    try {
      const res = await fetch('/api/admin/conversations');
      if (res.ok) setChats((await res.json()).conversations || []);
    } catch (err) { console.error(err); }
  };

  const fetchRagStats = async () => {
    try {
      const res = await fetch('/api/admin/rag/stats');
      if (res.ok) setRagStats(await res.json());
    } catch (err) { console.error(err); }
  };

  const fetchLlamaStats = async () => {
    try {
      const res = await fetch('/api/rag/llamaindex/stats');
      if (res.ok) setLlamaStats(await res.json());
    } catch (err) { console.error(err); }
  };

  const fetchLlamaConfig = async () => {
    try {
      const res = await fetch('/api/rag/llamaindex/config');
      if (res.ok) setLlamaConfig(await res.json());
    } catch (err) { console.error(err); }
  };

  const fetchCurrentChatId = async () => {
    try {
      const res = await fetch('/api/chat_id');
      if (res.ok) {
        const data = await res.json();
        setCurrentChatId(data.chat_id);
      }
    } catch (err) { console.error(err); }
  };

  // ============== Handler Functions ==============

  const handleSearch = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!query.trim() || isSearching) return;
    setIsSearching(true);
    setError(null);
    setResults(null);
    try {
      const res = await fetch(`/api/test/rag?query=${encodeURIComponent(query)}&k=8`);
      if (!res.ok) throw new Error('Search failed');
      setResults(await res.json());
    } catch (err) {
      setError('Search failed. Please try again.');
    } finally {
      setIsSearching(false);
    }
  };

  const handleLlamaSearch = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!llamaQuery.trim() || isLlamaSearching) return;
    setIsLlamaSearching(true);
    setLlamaResults(null);
    try {
      const res = await fetch('/api/rag/llamaindex/query', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ query: llamaQuery, top_k: llamaTopK })
      });
      if (!res.ok) throw new Error('Query failed');
      setLlamaResults(await res.json());
    } catch (err) {
      setError('LlamaIndex query failed.');
    } finally {
      setIsLlamaSearching(false);
    }
  };

  const handleSourceToggle = async (sourceName: string) => {
    const currentSelected = sources.filter(s => s.selected).map(s => s.name);
    const newSelected = currentSelected.includes(sourceName)
      ? currentSelected.filter(s => s !== sourceName)
      : [...currentSelected, sourceName];
    try {
      await fetch('/api/selected_sources', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(newSelected)
      });
      fetchSources();
      fetchRagStats();
    } catch (err) { console.error(err); }
  };

  const handleModelChange = async (newModel: string) => {
    try {
      await fetch('/api/selected_model', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ model: newModel })
      });
      setSelectedModel(newModel);
    } catch (err) { console.error(err); }
  };

  const handleSelectAll = async () => {
    try {
      await fetch('/api/admin/rag/sources/select-all', { method: 'POST' });
      fetchSources();
      fetchRagStats();
    } catch (err) { console.error(err); }
  };

  const handleDeselectAll = async () => {
    try {
      await fetch('/api/admin/rag/sources/deselect-all', { method: 'POST' });
      fetchSources();
      fetchRagStats();
    } catch (err) { console.error(err); }
  };

  const handleDeleteSource = async (sourceName: string) => {
    if (!confirm(`Delete source "${sourceName}"? This will also delete all vectors from the vector database. This cannot be undone.`)) return;
    try {
      const res = await fetch(`/api/collections/${encodeURIComponent(sourceName)}`, { method: 'DELETE' });
      const data = await res.json();
      if (res.ok) {
        alert(`Deleted: ${sourceName}`);
      } else {
        alert(`Error: ${data.detail || 'Unknown error'}`);
      }
      // Refresh all data after deletion
      fetchSources();
      fetchRagStats();
      fetchVectorStats();
    } catch (err) { 
      console.error(err);
      alert('Failed to delete source');
    }
  };

  const handleNewChat = async () => {
    try {
      await fetch('/api/chat/new', { method: 'POST' });
      fetchChats();
    } catch (err) { console.error(err); }
  };

  const handleDeleteChat = async (chatId: string) => {
    if (!confirm('Delete this chat?')) return;
    try {
      await fetch(`/api/chat/${chatId}`, { method: 'DELETE' });
      fetchChats();
    } catch (err) { console.error(err); }
  };

  const handleClearAllChats = async () => {
    if (!confirm('Delete ALL chats? This cannot be undone.')) return;
    try {
      await fetch('/api/chats/clear', { method: 'DELETE' });
      fetchChats();
    } catch (err) { console.error(err); }
  };

  const handleViewChatMessages = async (chatId: string) => {
    try {
      const res = await fetch(`/api/admin/conversations/${chatId}/messages`);
      if (res.ok) {
        setSelectedChatMessages((await res.json()).messages || []);
        setViewingChatId(chatId);
      }
    } catch (err) { console.error(err); }
  };

  const handleClearCache = async () => {
    try {
      await fetch('/api/rag/llamaindex/cache/clear', { method: 'POST' });
      fetchLlamaStats();
      alert('Cache cleared');
    } catch (err) { console.error(err); }
  };

  // File upload handler
  const handleFileUpload = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!uploadFiles || uploadFiles.length === 0) return;

    setIsUploading(true);
    setUploadMessage('');
    setUploadStatus('');

    try {
      const formData = new FormData();
      for (let i = 0; i < uploadFiles.length; i++) {
        formData.append('files', uploadFiles[i]);
      }

      const res = await fetch('/api/ingest', {
        method: 'POST',
        body: formData
      });

      const data = await res.json();
      setUploadMessage(data.message || 'Files uploaded');
      setUploadTaskId(data.task_id);
      setUploadStatus(data.status);

      // Poll for status if task_id exists
      if (data.task_id) {
        const pollStatus = async () => {
          const statusRes = await fetch(`/api/ingest/status/${data.task_id}`);
          if (statusRes.ok) {
            const statusData = await statusRes.json();
            setUploadStatus(statusData.status);
            if (statusData.status === 'completed' || statusData.status === 'failed') {
              return;
            }
            setTimeout(pollStatus, 2000);
          }
        };
        setTimeout(pollStatus, 2000);
      }

      fetchSources();
      fetchRagStats();
      fetchVectorStats();
    } catch (err) {
      setUploadMessage('Upload failed: ' + String(err));
    } finally {
      setIsUploading(false);
    }
  };

  // Chat rename handler
  const handleRenameChat = async (chatId: string) => {
    if (!newChatName.trim()) return;
    try {
      await fetch('/api/chat/rename', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ chat_id: chatId, new_name: newChatName })
      });
      setRenamingChatId(null);
      setNewChatName('');
      fetchChats();
    } catch (err) { console.error(err); }
  };

  const startRename = (chatId: string, currentName: string) => {
    setRenamingChatId(chatId);
    setNewChatName(currentName);
  };

  const selectedSources = sources.filter(s => s.selected);
  const unselectedSources = sources.filter(s => !s.selected);

  // ============== Render ==============

  if (isLoading) {
    return (
      <div className={styles.container}>
        <div className={styles.loadingContainer}>
          <div className={styles.spinner}></div>
          <p>Loading...</p>
        </div>
      </div>
    );
  }

  return (
    <div className={styles.container}>
      {/* Header */}
      <div className={styles.header}>
        <h1 className={styles.title}>RAG System Console</h1>
        <button 
          onClick={fetchAllData} 
          className={styles.backLink}
          style={{ background: '#f0f0f0', padding: '6px 12px', cursor: 'pointer' }}
        >
          🔄 Refresh All
        </button>
        <Link href="/" className={styles.backLink}>Back to Chat</Link>
      </div>

      {/* Current Session & Upload - Full Width */}
      <div className={styles.row}>
        {/* Current Session ID */}
        <div className={styles.panel}>
          <h2 className={styles.panelTitle}>Current Session</h2>
          {currentChatId ? (
            <div className={styles.infoList}>
              <div className={styles.infoItem}>
                <span className={styles.infoLabel}>Chat ID</span>
                <span className={styles.infoValue} style={{ fontSize: '12px', fontFamily: 'monospace' }}>{currentChatId}</span>
              </div>
            </div>
          ) : (
            <p className={styles.emptyState}>No active session</p>
          )}
        </div>

        {/* File Upload */}
        <div className={styles.panel}>
          <h2 className={styles.panelTitle}>Upload Documents</h2>
          <form onSubmit={handleFileUpload} style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
            <input
              type="file"
              multiple
              accept=".pdf,.txt,.doc,.docx"
              onChange={(e) => setUploadFiles(e.target.files)}
              className={styles.searchInput}
              style={{ padding: '0.5rem' }}
            />
            <button type="submit" className={styles.searchButton} disabled={isUploading || !uploadFiles || uploadFiles.length === 0}>
              {isUploading ? 'Uploading...' : 'Upload & Index'}
            </button>
          </form>
          {uploadMessage && (
            <div style={{ marginTop: '0.5rem', fontSize: '13px', color: uploadStatus === 'completed' ? 'green' : uploadStatus === 'failed' ? 'red' : '#666' }}>
              {uploadMessage}
              {uploadStatus && ` (${uploadStatus})`}
            </div>
          )}
        </div>
      </div>

      {/* Search Panel - Full Width */}
      <div className={`${styles.panel} ${styles.fullWidth}`}>
        <div className={styles.tabs}>
          <button className={`${styles.tab} ${activeTab === 'rag' ? styles.active : ''}`} onClick={() => setActiveTab('rag')}>
            Standard RAG
          </button>
          <button className={`${styles.tab} ${activeTab === 'llamaindex' ? styles.active : ''}`} onClick={() => setActiveTab('llamaindex')}>
            LlamaIndex RAG
          </button>
        </div>

        {activeTab === 'rag' ? (
          <>
            <form onSubmit={handleSearch} className={styles.searchForm}>
              <div style={{ display: 'flex', gap: '0.5rem' }}>
                <input
                  type="text"
                  value={query}
                  onChange={(e) => setQuery(e.target.value)}
                  placeholder="Enter search query..."
                  className={styles.searchInput}
                  style={{ flex: 1 }}
                />
                <button type="submit" className={styles.searchButton} disabled={isSearching || !query.trim()}>
                  {isSearching ? 'Searching...' : 'Search'}
                </button>
              </div>
            </form>

            {results && (
              <div className={styles.resultsContainer}>
                {results.answer && (
                  <div className={styles.answerSection}>
                    <div className={styles.answerLabel}>Generated Answer</div>
                    <div className={styles.answerContent}>{results.answer}</div>
                  </div>
                )}

                {results.retrieval_metadata && (
                  <div className={styles.retrievalMeta}>
                    <div className={styles.metaItem}>
                      <div className={styles.metaValue}>{results.retrieval_metadata.total_chunks_retrieved}</div>
                      <div className={styles.metaLabel}>Chunks</div>
                    </div>
                    <div className={styles.metaItem}>
                      <div className={styles.metaValue}>{results.retrieval_metadata.unique_sources_count}</div>
                      <div className={styles.metaLabel}>Sources</div>
                    </div>
                    <div className={styles.metaItem}>
                      <div className={styles.metaValue}>{(results.retrieval_metadata.score_range.avg * 100).toFixed(1)}%</div>
                      <div className={styles.metaLabel}>Avg Score</div>
                    </div>
                  </div>
                )}

                {results.sources?.map((src, idx) => (
                  <div key={idx} className={styles.resultItem} style={{ marginTop: '1rem' }}>
                    <div className={styles.resultHeader}>
                      <span className={styles.resultTitle}>{src.name}</span>
                      <span className={styles.resultScore}>{(src.max_score * 100).toFixed(1)}%</span>
                    </div>
                    <div className={styles.resultChunkCount}>{src.chunk_count} chunks</div>
                    {src.chunks?.[0] && <div className={styles.resultContent}>{src.chunks[0].excerpt}</div>}
                  </div>
                ))}
              </div>
            )}
          </>
        ) : (
          <>
            <form onSubmit={handleLlamaSearch} className={styles.searchForm}>
              <div style={{ display: 'flex', gap: '0.5rem' }}>
                <input
                  type="text"
                  value={llamaQuery}
                  onChange={(e) => setLlamaQuery(e.target.value)}
                  placeholder="Enter query for LlamaIndex..."
                  className={styles.searchInput}
                  style={{ flex: 1 }}
                />
                <select
                  value={llamaTopK}
                  onChange={(e) => setLlamaTopK(Number(e.target.value))}
                  className={styles.select}
                  style={{ width: '100px' }}
                >
                  <option value={5}>Top 5</option>
                  <option value={10}>Top 10</option>
                  <option value={20}>Top 20</option>
                </select>
                <button type="submit" className={styles.searchButton} disabled={isLlamaSearching || !llamaQuery.trim()}>
                  {isLlamaSearching ? 'Querying...' : 'Query'}
                </button>
              </div>
            </form>

            {llamaResults && (
              <div className={styles.resultsContainer}>
                {llamaResults.answer && (
                  <div className={styles.answerSection}>
                    <div className={styles.answerLabel}>Generated Answer</div>
                    <div className={styles.answerContent}>{llamaResults.answer}</div>
                  </div>
                )}
                {llamaResults.sources?.map((src: any, idx: number) => (
                  <div key={idx} className={styles.resultItem} style={{ marginTop: '1rem' }}>
                    <div className={styles.resultHeader}>
                      <span className={styles.resultTitle}>{src.name}</span>
                    </div>
                    <div className={styles.resultContent}>{src.excerpt}</div>
                  </div>
                ))}
              </div>
            )}
          </>
        )}
      </div>

      {/* Knowledge Sources - Full Width - Most Important */}
      <div className={`${styles.panel} ${styles.fullWidth}`}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1rem' }}>
          <h2 className={styles.panelTitle} style={{ margin: 0 }}>
            Knowledge Sources ({sources.length})
          </h2>
          <div className={styles.buttonGroup}>
            <button onClick={handleSelectAll} className={`${styles.button} ${styles.buttonPrimary}`}>Select All</button>
            <button onClick={handleDeselectAll} className={`${styles.button} ${styles.buttonSecondary}`}>Deselect All</button>
            <button onClick={fetchSources} className={`${styles.button} ${styles.buttonSecondary}`}>Refresh</button>
          </div>
        </div>

        {/* Selected Sources */}
        <div className={styles.sourceSection}>
          <div className={styles.sourceSectionHeader}>
            <span className={styles.sourceSectionTitle}>Active Sources ({selectedSources.length})</span>
            <span className={`${styles.sourceCount} ${styles.selected}`}>{selectedSources.length} selected</span>
          </div>
          {selectedSources.length > 0 ? (
            <div className={styles.sourcesList}>
              {selectedSources.map(source => (
                <div key={source.name} className={`${styles.sourceItem} ${styles.selected}`}>
                  <input
                    type="checkbox"
                    className={styles.sourceCheckbox}
                    checked={true}
                    onChange={() => handleSourceToggle(source.name)}
                  />
                  <span className={styles.sourceName}>{source.name}</span>
                  <button className={styles.deleteBtn} onClick={() => handleDeleteSource(source.name)} title="Delete">Delete</button>
                </div>
              ))}
            </div>
          ) : (
            <div className={styles.emptyState}><p>No sources selected. Select sources below for RAG search.</p></div>
          )}
        </div>

        {/* Unselected Sources */}
        {unselectedSources.length > 0 && (
          <div className={styles.sourceSection}>
            <div className={styles.sourceSectionHeader}>
              <span className={styles.sourceSectionTitle}>Available Sources ({unselectedSources.length})</span>
              <span className={`${styles.sourceCount} ${styles.unselected}`}>{unselectedSources.length} available</span>
            </div>
            <div className={styles.sourcesList} style={{ maxHeight: '200px' }}>
              {unselectedSources.map(source => (
                <div key={source.name} className={styles.sourceItem}>
                  <input
                    type="checkbox"
                    className={styles.sourceCheckbox}
                    checked={false}
                    onChange={() => handleSourceToggle(source.name)}
                  />
                  <span className={styles.sourceName}>{source.name}</span>
                  <button className={styles.deleteBtn} onClick={() => handleDeleteSource(source.name)} title="Delete">Delete</button>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>

      {/* Stats Row */}
      <div className={styles.row}>
        {/* Vector Stats */}
        <div className={styles.panel}>
          <h2 className={styles.panelTitle}>Vector Database</h2>
          <div className={styles.statsGrid}>
            <div className={styles.statCard}>
              <div className={styles.statValue}>{vectorStats?.total_entities?.toLocaleString() || '0'}</div>
              <div className={styles.statLabel}>Total Vectors</div>
            </div>
            <div className={styles.statCard}>
              <div className={styles.statValue}>{ragStats?.documents.total_count || '0'}</div>
              <div className={styles.statLabel}>Total Docs</div>
            </div>
            <div className={styles.statCard}>
              <div className={styles.statValue} style={{ color: selectedSources.length > 0 ? 'green' : 'orange' }}>
                {selectedSources.length}
              </div>
              <div className={styles.statLabel}>Selected</div>
            </div>
            <div className={styles.statCard}>
              <div className={styles.statValue}>{ragStats?.conversations.total_count || '0'}</div>
              <div className={styles.statLabel}>Sessions</div>
            </div>
          </div>
          {/* Vector Details */}
          {vectorStats && (
            <div className={styles.infoList} style={{ marginTop: '1rem' }}>
              <div className={styles.infoItem}>
                <span className={styles.infoLabel}>💡 Tip</span>
                <span className={styles.infoValue} style={{ fontSize: '12px' }}>
                  {selectedSources.length === 0 ? 'Select sources below to enable RAG search!' : `${selectedSources.length} sources selected for search`}
                </span>
              </div>
              <div className={styles.infoItem}>
                <span className={styles.infoLabel}>Avg Vectors/Doc</span>
                <span className={styles.infoValue}>
                  {ragStats?.documents.total_count ? 
                    Math.round(vectorStats.total_entities / ragStats.documents.total_count).toLocaleString() 
                    : '0'}
                </span>
              </div>
              <div className={styles.infoItem}>
                <span className={styles.infoLabel}>Status</span>
                <span className={styles.infoValue} style={{ color: vectorStats.total_entities > 0 ? 'green' : 'orange' }}>
                  {vectorStats.total_entities > 0 ? '✓ Ready' : '⚠ Empty'}
                </span>
              </div>
            </div>
          )}
        </div>

        {/* Model Management */}
        <div className={styles.panel}>
          <h2 className={styles.panelTitle}>Model</h2>
          <select
            value={selectedModel}
            onChange={(e) => handleModelChange(e.target.value)}
            className={styles.select}
          >
            {availableModels.map(m => <option key={m} value={m}>{m}</option>)}
          </select>
          <div className={styles.infoList} style={{ marginTop: '1rem' }}>
            <div className={styles.infoItem}><span className={styles.infoLabel}>Available</span><span className={styles.infoValue}>{availableModels.length}</span></div>
            <div className={styles.infoItem}><span className={styles.infoLabel}>Current</span><span className={styles.infoValue}>{selectedModel || 'None'}</span></div>
          </div>
        </div>
      </div>

      {/* Session Management */}
      <div className={`${styles.panel} ${styles.fullWidth}`}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1rem' }}>
          <h2 className={styles.panelTitle} style={{ margin: 0 }}>Sessions ({chats.length})</h2>
          <div className={styles.buttonGroup}>
            <button onClick={handleNewChat} className={`${styles.button} ${styles.buttonPrimary}`}>New Chat</button>
            <button onClick={handleClearAllChats} className={`${styles.button} ${styles.buttonDanger}`}>Clear All</button>
          </div>
        </div>
        {chats.length > 0 ? (
          <div className={styles.chatList} style={{ maxHeight: '200px' }}>
            {chats.map(chat => (
              <div key={chat.chat_id} className={styles.chatItem}>
                {renamingChatId === chat.chat_id ? (
                  <div style={{ display: 'flex', gap: '0.5rem', flex: 1, alignItems: 'center' }}>
                    <input
                      type="text"
                      value={newChatName}
                      onChange={(e) => setNewChatName(e.target.value)}
                      className={styles.searchInput}
                      style={{ flex: 1, padding: '0.25rem 0.5rem' }}
                      autoFocus
                      onKeyDown={(e) => {
                        if (e.key === 'Enter') handleRenameChat(chat.chat_id);
                        if (e.key === 'Escape') { setRenamingChatId(null); setNewChatName(''); }
                      }}
                    />
                    <button className={styles.chatActionBtn} onClick={() => handleRenameChat(chat.chat_id)}>Save</button>
                    <button className={styles.chatActionBtn} onClick={() => { setRenamingChatId(null); setNewChatName(''); }}>Cancel</button>
                  </div>
                ) : (
                  <>
                    <span className={styles.chatItemName}>{chat.name}</span>
                    <div className={styles.chatItemActions}>
                      <button className={styles.chatActionBtn} onClick={() => startRename(chat.chat_id, chat.name)}>Rename</button>
                      <button className={styles.chatActionBtn} onClick={() => handleViewChatMessages(chat.chat_id)}>View</button>
                      <button className={styles.chatActionBtn} onClick={() => handleDeleteChat(chat.chat_id)}>Delete</button>
                    </div>
                  </>
                )}
              </div>
            ))}
          </div>
        ) : (
          <div className={styles.emptyState}><p>No sessions</p></div>
        )}
      </div>

      {/* LlamaIndex Info */}
      <div className={styles.row}>
        <div className={styles.panel}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1rem' }}>
            <h2 className={styles.panelTitle} style={{ margin: 0 }}>LlamaIndex</h2>
            <button onClick={handleClearCache} className={`${styles.button} ${styles.buttonSecondary}`}>Clear Cache</button>
          </div>
          {llamaStats && (
            <div className={styles.infoList}>
              <div className={styles.infoItem}><span className={styles.infoLabel}>Collection</span><span className={styles.infoValue}>{llamaStats.index.collection}</span></div>
              <div className={styles.infoItem}><span className={styles.infoLabel}>Embedding Dim</span><span className={styles.infoValue}>{llamaStats.index.embedding_dimensions}</span></div>
              <div className={styles.infoItem}><span className={styles.infoLabel}>Cache Enabled</span><span className={styles.infoValue}>{llamaStats.cache.enabled ? 'Yes' : 'No'}</span></div>
              <div className={styles.infoItem}><span className={styles.infoLabel}>Cached Queries</span><span className={styles.infoValue}>{llamaStats.cache.cached_queries}</span></div>
              {llamaConfig && (
                <div className={styles.infoList}>
                  <div className={styles.infoItem}><span className={styles.infoLabel}>Hybrid Search</span><span className={styles.infoValue}>{llamaConfig.features.hybrid_search ? 'Yes' : 'No'}</span></div>
                  <div className={styles.infoItem}><span className={styles.infoLabel}>Chunk Strategy</span><span className={styles.infoValue}>{llamaConfig.default_chunk_strategy}</span></div>
                  <div className={styles.infoItem}><span className={styles.infoLabel}>Default Top-K</span><span className={styles.infoValue}>{llamaConfig.default_top_k}</span></div>
                </div>
              )}
            </div>
          )}
        </div>

        <div className={styles.panel}>
          <h2 className={styles.panelTitle}>System Status</h2>
          {ragStats && (
            <div className={styles.infoList}>
              <div className={styles.infoItem}><span className={styles.infoLabel}>Total Docs</span><span className={styles.infoValue}>{ragStats.documents.total_count}</span></div>
              <div className={styles.infoItem}><span className={styles.infoLabel}>Selected</span><span className={styles.infoValue}>{ragStats.documents.selected_count}</span></div>
              <div className={styles.infoItem}><span className={styles.infoLabel}>Unselected</span><span className={styles.infoValue}>{ragStats.documents.unselected_count}</span></div>
              <div className={styles.infoItem}><span className={styles.infoLabel}>Sessions</span><span className={styles.infoValue}>{ragStats.conversations.total_count}</span></div>
            </div>
          )}
        </div>
      </div>

      {/* Chat Messages Modal */}
      {viewingChatId && (
        <div style={{
          position: 'fixed', top: 0, left: 0, right: 0, bottom: 0,
          background: 'rgba(0,0,0,0.5)', display: 'flex', alignItems: 'center', justifyContent: 'center',
          zIndex: 1000
        }} onClick={() => setViewingChatId(null)}>
          <div style={{
            background: 'white', padding: '1.5rem', borderRadius: '12px', maxWidth: '600px', width: '90%',
            maxHeight: '80vh', overflow: 'auto'
          }} onClick={e => e.stopPropagation()}>
            <h3 style={{ marginTop: 0 }}>Chat Messages</h3>
            <div className={styles.messagesContainer}>
              {selectedChatMessages.map((msg, idx) => (
                <div key={idx} className={`${styles.message} ${
                  msg.type === 'HumanMessage' ? styles.messageHuman :
                  msg.type === 'AIMessage' ? styles.messageAI : styles.messageSystem
                }`}>
                  <strong>{msg.type}:</strong> {msg.content}
                </div>
              ))}
            </div>
            <button onClick={() => setViewingChatId(null)} className={`${styles.button} ${styles.buttonPrimary}`} style={{ marginTop: '1rem' }}>
              Close
            </button>
          </div>
        </div>
      )}
    </div>
  );
}

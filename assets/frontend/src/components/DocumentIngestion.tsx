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
import { SetStateAction, useState, useEffect, useRef } from 'react';
import styles from '@/styles/DocumentIngestion.module.css';

declare module 'react' {
  interface InputHTMLAttributes<T> extends HTMLAttributes<T> {
    webkitdirectory?: string;
    directory?: string;
  }
}

interface DocumentIngestionProps {
  files: FileList | null;
  ingestMessage: string;
  isIngesting: boolean;
  setFiles: (files: FileList | null) => void;
  setIngestMessage: (message: string) => void;
  setIsIngesting: (value: boolean) => void;
  onSuccessfulIngestion?: () => void;
}

type IngestStatus = 'idle' | 'queued' | 'saving_files' | 'loading_documents' | 'indexing_documents' | 'completed' | 'failed';

export default function DocumentIngestion({
  files,
  ingestMessage,
  isIngesting,
  setFiles,
  setIngestMessage,
  setIsIngesting,
  onSuccessfulIngestion
}: DocumentIngestionProps) {
  const [taskId, setTaskId] = useState<string | null>(null);
  const [ingestStatus, setIngestStatus] = useState<IngestStatus>('idle');
  const [progressPercent, setProgressPercent] = useState(0);
  const statusPollRef = useRef<NodeJS.Timeout | null>(null);

  // Poll ingest status when we have a taskId
  useEffect(() => {
    if (taskId && isIngesting) {
      const pollStatus = async () => {
        try {
          const response = await fetch(`/api/ingest/status/${taskId}`);
          if (response.ok) {
            const data = await response.json();
            setIngestStatus(data.status);

            // Calculate progress based on status
            const statusProgress: Record<IngestStatus, number> = {
              'idle': 0,
              'queued': 10,
              'saving_files': 30,
              'loading_documents': 50,
              'indexing_documents': 70,
              'completed': 100,
              'failed': 0
            };
            setProgressPercent(statusProgress[data.status as IngestStatus] || 0);

            // Stop polling if completed or failed
            if (data.status === 'completed' || data.status === 'failed') {
              if (statusPollRef.current) {
                clearInterval(statusPollRef.current);
              }
              setIsIngesting(false);
              if (data.status === 'completed' && onSuccessfulIngestion) {
                onSuccessfulIngestion();
              }
            }
          }
        } catch (error) {
          console.error("Error polling ingest status:", error);
        }
      };

      // Poll every 2 seconds
      statusPollRef.current = setInterval(pollStatus, 2000);
      pollStatus(); // Initial poll
    }

    return () => {
      if (statusPollRef.current) {
        clearInterval(statusPollRef.current);
      }
    };
  }, [taskId, isIngesting, onSuccessfulIngestion, setIsIngesting]);

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    setFiles(e.target.files);
  };

  const handleIngestSubmit = async (e: { preventDefault: () => void }) => {
    e.preventDefault();
    setIsIngesting(true);
    setIngestMessage("");
    setIngestStatus('queued');
    setProgressPercent(5);

    try {
      if (files && files.length > 0) {
        const formData = new FormData();
        for (let i = 0; i < files.length; i++) {
          formData.append("files", files[i]);
        }

        const res = await fetch("/api/ingest", {
          method: "POST",
          body: formData,
        });

        const data = await res.json();
        setIngestMessage(data.message);

        // Store taskId for status polling
        if (data.task_id) {
          setTaskId(data.task_id);
        }

        // If the response indicates immediate completion (old behavior)
        if (data.status === 'completed') {
          setIngestStatus('completed');
          setProgressPercent(100);
          setIsIngesting(false);
          if (onSuccessfulIngestion) {
            onSuccessfulIngestion();
          }
        }
      } else {
        setIngestMessage("Please select files or specify a directory path.");
        setIsIngesting(false);
      }
    } catch (error) {
      console.error("Error during ingestion:", error);
      setIngestMessage("Error during ingestion. Please check the console for details.");
      setIngestStatus('failed');
      setIsIngesting(false);
    }
  };

  const handleDragOver = (e: React.DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    e.stopPropagation();
  };

  const handleDrop = (e: React.DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    e.stopPropagation();
    if (e.dataTransfer.files && e.dataTransfer.files.length > 0) {
      setFiles(e.dataTransfer.files);
    }
  };

  const getStatusText = (status: IngestStatus): string => {
    const statusTexts: Record<IngestStatus, string> = {
      'idle': 'Ready',
      'queued': 'Queued for processing...',
      'saving_files': 'Saving files...',
      'loading_documents': 'Loading documents...',
      'indexing_documents': 'Indexing documents...',
      'completed': 'Completed!',
      'failed': 'Failed'
    };
    return statusTexts[status] || 'Processing...';
  };

  return (
    <div className={styles.section}>
      <h1>Document Ingestion</h1>
      <form onSubmit={handleIngestSubmit} className={styles.ingestForm}>
        <div
          className={styles.uploadSection}
          onDragOver={handleDragOver}
          onDrop={handleDrop}
        >
          <label htmlFor="file-upload" className={styles.customFileLabel}>
            Choose Files
          </label>
          <input
            id="file-upload"
            type="file"
            multiple
            onChange={handleFileChange}
            disabled={isIngesting}
            className={styles.fileInput}
          />
          <span className={styles.fileName}>
            {files && files.length > 0 ? Array.from(files).map(f => f.name).join(', ') : "No file chosen"}
          </span>
          <p className={styles.helpText}>
            Select files or drag and drop them here
          </p>
        </div>

        {/* Progress Bar */}
        {isIngesting && (
          <div className={styles.progressContainer}>
            <div className={styles.progressBar}>
              <div
                className={styles.progressFill}
                style={{ width: `${progressPercent}%` }}
              />
            </div>
            <span className={styles.progressText}>{getStatusText(ingestStatus)}</span>
          </div>
        )}

        <button
          type="submit"
          disabled={isIngesting || !files}
          className={styles.ingestButton}
        >
          {isIngesting ? "Ingesting..." : "Ingest Documents"}
        </button>
      </form>

      {ingestMessage && (
        <div className={styles.messageContainer}>
          <p>{ingestMessage}</p>
        </div>
      )}
    </div>
  );
} 
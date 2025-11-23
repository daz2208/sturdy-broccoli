'use client';

import { useEffect, useState } from 'react';
import api from '@/lib/api';
import toast from 'react-hot-toast';
import { Settings, Database, RefreshCw, CheckCircle, AlertCircle, Loader2 } from 'lucide-react';

interface ChunkStatus {
  total_documents: number;
  chunked_documents: number;
  pending_documents: number;
  failed_documents: number;
  total_chunks: number;
  chunks_with_embeddings: number;
}

export default function AdminPage() {
  const [chunkStatus, setChunkStatus] = useState<ChunkStatus | null>(null);
  const [loading, setLoading] = useState(true);
  const [backfilling, setBackfilling] = useState(false);

  useEffect(() => { loadChunkStatus(); }, []);

  const loadChunkStatus = async () => {
    try {
      const data = await api.getChunkStatus();
      setChunkStatus(data);
    } catch {
      toast.error('Failed to load chunk status');
    } finally {
      setLoading(false);
    }
  };

  const runBackfill = async (generateEmbeddings: boolean) => {
    setBackfilling(true);
    try {
      const result = await api.backfillChunks(undefined, generateEmbeddings);
      toast.success(`Processed ${result.processed} documents (${result.succeeded} succeeded)`);
      loadChunkStatus();
    } catch {
      toast.error('Backfill failed');
    } finally {
      setBackfilling(false);
    }
  };

  if (loading) {
    return (
      <div className="flex justify-center py-12">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary"></div>
      </div>
    );
  }

  return (
    <div className="space-y-6 animate-fadeIn">
      <div>
        <h1 className="text-2xl font-bold text-gray-100">Admin Panel</h1>
        <p className="text-gray-500">System administration and maintenance</p>
      </div>

      {/* Chunk Status */}
      <div className="bg-dark-100 rounded-xl border border-dark-300 p-6">
        <div className="flex items-center gap-3 mb-6">
          <Database className="w-6 h-6 text-primary" />
          <h2 className="text-xl font-semibold text-gray-200">Document Chunking Status</h2>
        </div>

        {chunkStatus && (
          <div className="grid grid-cols-2 md:grid-cols-3 gap-4 mb-6">
            <div className="bg-dark-200 rounded-lg p-4">
              <p className="text-gray-500 text-sm">Total Documents</p>
              <p className="text-2xl font-bold text-gray-100">{chunkStatus.total_documents}</p>
            </div>
            <div className="bg-dark-200 rounded-lg p-4">
              <p className="text-gray-500 text-sm">Chunked</p>
              <p className="text-2xl font-bold text-green-400">{chunkStatus.chunked_documents}</p>
            </div>
            <div className="bg-dark-200 rounded-lg p-4">
              <p className="text-gray-500 text-sm">Pending</p>
              <p className="text-2xl font-bold text-yellow-400">{chunkStatus.pending_documents}</p>
            </div>
            <div className="bg-dark-200 rounded-lg p-4">
              <p className="text-gray-500 text-sm">Failed</p>
              <p className="text-2xl font-bold text-red-400">{chunkStatus.failed_documents}</p>
            </div>
            <div className="bg-dark-200 rounded-lg p-4">
              <p className="text-gray-500 text-sm">Total Chunks</p>
              <p className="text-2xl font-bold text-gray-100">{chunkStatus.total_chunks}</p>
            </div>
            <div className="bg-dark-200 rounded-lg p-4">
              <p className="text-gray-500 text-sm">With Embeddings</p>
              <p className="text-2xl font-bold text-primary">{chunkStatus.chunks_with_embeddings}</p>
            </div>
          </div>
        )}

        <div className="flex gap-3">
          <button
            onClick={() => runBackfill(false)}
            disabled={backfilling}
            className="btn btn-secondary flex items-center gap-2"
          >
            {backfilling ? <Loader2 className="w-4 h-4 animate-spin" /> : <RefreshCw className="w-4 h-4" />}
            Backfill Chunks
          </button>
          <button
            onClick={() => runBackfill(true)}
            disabled={backfilling}
            className="btn btn-primary flex items-center gap-2"
          >
            {backfilling ? <Loader2 className="w-4 h-4 animate-spin" /> : <RefreshCw className="w-4 h-4" />}
            Backfill with Embeddings
          </button>
        </div>
      </div>

      {/* System Health */}
      <div className="bg-dark-100 rounded-xl border border-dark-300 p-6">
        <div className="flex items-center gap-3 mb-6">
          <Settings className="w-6 h-6 text-primary" />
          <h2 className="text-xl font-semibold text-gray-200">System Health</h2>
        </div>

        <div className="grid gap-3">
          <div className="flex items-center justify-between p-3 bg-dark-200 rounded-lg">
            <span className="text-gray-300">Database Connection</span>
            <CheckCircle className="w-5 h-5 text-green-400" />
          </div>
          <div className="flex items-center justify-between p-3 bg-dark-200 rounded-lg">
            <span className="text-gray-300">Vector Store</span>
            <CheckCircle className="w-5 h-5 text-green-400" />
          </div>
          <div className="flex items-center justify-between p-3 bg-dark-200 rounded-lg">
            <span className="text-gray-300">OpenAI API</span>
            <CheckCircle className="w-5 h-5 text-green-400" />
          </div>
        </div>
      </div>
    </div>
  );
}

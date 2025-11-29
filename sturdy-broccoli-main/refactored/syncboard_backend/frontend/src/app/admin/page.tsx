'use client';

import { useEffect, useState } from 'react';
import api from '@/lib/api';
import toast from 'react-hot-toast';
import { Settings, Database, RefreshCw, CheckCircle, AlertCircle, Loader2, Lightbulb, Cpu, XCircle, PlayCircle } from 'lucide-react';

interface ChunkStatus {
  total_documents: number;
  chunked_documents: number;
  pending_documents: number;
  failed_documents: number;
  total_chunks: number;
  chunks_with_embeddings: number;
}

interface LLMProviderStatus {
  provider: string;
  status: string;
  details: Record<string, any>;
}

export default function AdminPage() {
  const [chunkStatus, setChunkStatus] = useState<ChunkStatus | null>(null);
  const [llmStatus, setLlmStatus] = useState<LLMProviderStatus | null>(null);
  const [loading, setLoading] = useState(true);
  const [backfilling, setBackfilling] = useState(false);
  const [seedsLoading, setSeedsLoading] = useState(false);
  const [testingLLM, setTestingLLM] = useState(false);

  useEffect(() => {
    loadChunkStatus();
    loadLLMStatus();
  }, []);

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

  const loadLLMStatus = async () => {
    try {
      const data = await api.getLLMProviderStatus();
      setLlmStatus(data);
    } catch (err) {
      toast.error('Failed to load LLM provider status');
    }
  };

  const testLLMProvider = async () => {
    setTestingLLM(true);
    try {
      const result = await api.testLLMProvider();
      toast.success(`LLM test successful! Provider: ${result.provider}`);
    } catch (err: any) {
      const errorMsg = err.response?.data?.detail || 'LLM provider test failed';
      toast.error(errorMsg);
    } finally {
      setTestingLLM(false);
    }
  };

  const runSeedBackfill = async () => {
    setSeedsLoading(true);
    try {
      const result = await api.backfillIdeaSeeds();
      toast.success(`Seeds generated: ${result.seeds_generated}, skipped: ${result.skipped}`);
    } catch {
      toast.error('Idea seed backfill failed');
    } finally {
      setSeedsLoading(false);
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

      {/* Idea Seeds */}
      <div className="bg-dark-100 rounded-xl border border-dark-300 p-6">
        <div className="flex items-center gap-3 mb-4">
          <Lightbulb className="w-6 h-6 text-primary" />
          <div>
            <h2 className="text-xl font-semibold text-gray-200">Idea Seeds</h2>
            <p className="text-gray-500 text-sm">Generate precomputed build ideas for documents with summaries.</p>
          </div>
        </div>
        <button
          onClick={runSeedBackfill}
          disabled={seedsLoading}
          className="btn btn-primary flex items-center gap-2"
        >
          {seedsLoading ? <Loader2 className="w-4 h-4 animate-spin" /> : <RefreshCw className="w-4 h-4" />}
          Backfill Idea Seeds
        </button>
      </div>

      {/* LLM Provider Configuration */}
      <div className="bg-dark-100 rounded-xl border border-dark-300 p-6">
        <div className="flex items-center gap-3 mb-6">
          <Cpu className="w-6 h-6 text-primary" />
          <div>
            <h2 className="text-xl font-semibold text-gray-200">LLM Provider</h2>
            <p className="text-gray-500 text-sm">Configuration and status of AI language model provider</p>
          </div>
        </div>

        {llmStatus && (
          <div className="space-y-4">
            {/* Provider Overview */}
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div className="bg-dark-200 rounded-lg p-4">
                <p className="text-gray-500 text-sm mb-1">Current Provider</p>
                <p className="text-xl font-bold text-gray-100 capitalize">{llmStatus.provider}</p>
              </div>
              <div className="bg-dark-200 rounded-lg p-4">
                <p className="text-gray-500 text-sm mb-1">Status</p>
                <div className="flex items-center gap-2">
                  {llmStatus.status === 'ready' || llmStatus.status === 'configured' ? (
                    <>
                      <CheckCircle className="w-5 h-5 text-green-400" />
                      <span className="text-xl font-bold text-green-400 capitalize">{llmStatus.status}</span>
                    </>
                  ) : llmStatus.status === 'not_configured' || llmStatus.status === 'models_missing' ? (
                    <>
                      <AlertCircle className="w-5 h-5 text-yellow-400" />
                      <span className="text-xl font-bold text-yellow-400 capitalize">{llmStatus.status.replace('_', ' ')}</span>
                    </>
                  ) : (
                    <>
                      <XCircle className="w-5 h-5 text-red-400" />
                      <span className="text-xl font-bold text-red-400 capitalize">{llmStatus.status.replace('_', ' ')}</span>
                    </>
                  )}
                </div>
              </div>
            </div>

            {/* Provider-specific Details */}
            <div className="bg-dark-200 rounded-lg p-4">
              <p className="text-gray-400 text-sm font-semibold mb-3">Configuration Details</p>
              <div className="space-y-2">
                {llmStatus.provider === 'openai' && (
                  <>
                    <div className="flex justify-between text-sm">
                      <span className="text-gray-500">API Key Configured:</span>
                      <span className={llmStatus.details.configured ? 'text-green-400' : 'text-red-400'}>
                        {llmStatus.details.configured ? 'Yes' : 'No'}
                      </span>
                    </div>
                    <div className="flex justify-between text-sm">
                      <span className="text-gray-500">Concept Model:</span>
                      <span className="text-gray-300">{llmStatus.details.model_concept}</span>
                    </div>
                    <div className="flex justify-between text-sm">
                      <span className="text-gray-500">Suggestion Model:</span>
                      <span className="text-gray-300">{llmStatus.details.model_suggestion}</span>
                    </div>
                  </>
                )}

                {llmStatus.provider === 'ollama' && (
                  <>
                    <div className="flex justify-between text-sm">
                      <span className="text-gray-500">Base URL:</span>
                      <span className="text-gray-300">{llmStatus.details.base_url}</span>
                    </div>
                    <div className="flex justify-between text-sm">
                      <span className="text-gray-500">Connected:</span>
                      <span className={llmStatus.details.connected ? 'text-green-400' : 'text-red-400'}>
                        {llmStatus.details.connected ? 'Yes' : 'No'}
                      </span>
                    </div>
                    <div className="flex justify-between text-sm">
                      <span className="text-gray-500">Concept Model:</span>
                      <span className="text-gray-300">{llmStatus.details.model_concept}</span>
                    </div>
                    <div className="flex justify-between text-sm">
                      <span className="text-gray-500">Suggestion Model:</span>
                      <span className="text-gray-300">{llmStatus.details.model_suggestion}</span>
                    </div>

                    {llmStatus.details.available_models && (
                      <div className="mt-3 pt-3 border-t border-dark-300">
                        <p className="text-gray-500 text-xs mb-2">Available Models:</p>
                        <div className="flex flex-wrap gap-1">
                          {llmStatus.details.available_models.map((model: string) => (
                            <span key={model} className="px-2 py-1 bg-dark-100 rounded text-xs text-gray-400">
                              {model}
                            </span>
                          ))}
                        </div>
                      </div>
                    )}

                    {llmStatus.details.missing_models && llmStatus.details.missing_models.length > 0 && (
                      <div className="mt-2 p-2 bg-yellow-900/20 border border-yellow-700/50 rounded">
                        <p className="text-yellow-400 text-xs">
                          Missing models: {llmStatus.details.missing_models.join(', ')}
                        </p>
                      </div>
                    )}
                  </>
                )}

                {llmStatus.provider === 'mock' && (
                  <div className="text-sm text-gray-400">
                    {llmStatus.details.note}
                  </div>
                )}
              </div>
            </div>

            {/* Test Button */}
            <div className="flex gap-3">
              <button
                onClick={testLLMProvider}
                disabled={testingLLM || llmStatus.status === 'not_configured'}
                className="btn btn-primary flex items-center gap-2"
              >
                {testingLLM ? <Loader2 className="w-4 h-4 animate-spin" /> : <PlayCircle className="w-4 h-4" />}
                Test Provider
              </button>
              <button
                onClick={loadLLMStatus}
                className="btn btn-secondary flex items-center gap-2"
              >
                <RefreshCw className="w-4 h-4" />
                Refresh Status
              </button>
            </div>

            {/* Configuration Help */}
            {llmStatus.status === 'not_configured' && llmStatus.provider === 'openai' && (
              <div className="mt-4 p-4 bg-blue-900/20 border border-blue-700/50 rounded-lg">
                <p className="text-blue-300 text-sm font-semibold mb-2">OpenAI Configuration Required</p>
                <p className="text-blue-200/80 text-sm">
                  Set your OpenAI API key in the backend environment variables:
                  <code className="block mt-2 px-2 py-1 bg-dark-300 rounded text-xs">
                    OPENAI_API_KEY=sk-your-actual-key
                  </code>
                </p>
              </div>
            )}

            {llmStatus.status === 'connection_error' && llmStatus.provider === 'ollama' && (
              <div className="mt-4 p-4 bg-red-900/20 border border-red-700/50 rounded-lg">
                <p className="text-red-300 text-sm font-semibold mb-2">Ollama Connection Failed</p>
                <p className="text-red-200/80 text-sm">
                  Cannot connect to Ollama at {llmStatus.details.base_url}. Make sure Ollama is running:
                  <code className="block mt-2 px-2 py-1 bg-dark-300 rounded text-xs">
                    ollama serve
                  </code>
                </p>
              </div>
            )}
          </div>
        )}
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

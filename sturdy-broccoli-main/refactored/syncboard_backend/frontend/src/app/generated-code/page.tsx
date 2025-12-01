'use client';

import { useEffect, useState } from 'react';
import api from '@/lib/api';
import toast from 'react-hot-toast';
import { Code, Download, Trash2, FileCode, Archive } from 'lucide-react';
import type { GeneratedCode } from '@/types/api';

const LANGUAGE_COLORS: Record<string, string> = {
  python: 'text-yellow-400 bg-yellow-400/10',
  javascript: 'text-yellow-300 bg-yellow-300/10',
  typescript: 'text-blue-400 bg-blue-400/10',
  rust: 'text-orange-400 bg-orange-400/10',
  go: 'text-cyan-400 bg-cyan-400/10',
  java: 'text-red-400 bg-red-400/10',
  default: 'text-gray-400 bg-gray-400/10',
};

export default function GeneratedCodePage() {
  const [codeFiles, setCodeFiles] = useState<GeneratedCode[]>([]);
  const [loading, setLoading] = useState(true);
  const [filter, setFilter] = useState<string>('');
  const [deleting, setDeleting] = useState<number | null>(null);

  // eslint-disable-next-line react-hooks/exhaustive-deps
  useEffect(() => { loadCode(); }, [filter]);

  const loadCode = async () => {
    try {
      const data = await api.getGeneratedCode(undefined, filter || undefined);
      setCodeFiles(Array.isArray(data) ? data : []);
    } catch {
      toast.error('Failed to load generated code');
    } finally {
      setLoading(false);
    }
  };

  const downloadCode = (id: number) => {
    window.open(api.getCodeDownloadUrl(id), '_blank');
  };

  const deleteCode = async (id: number) => {
    if (!confirm('Delete this code file?')) return;
    setDeleting(id);
    try {
      await api.deleteGeneratedCode(id);
      toast.success('Code file deleted');
      loadCode();
    } catch {
      toast.error('Failed to delete code file');
    } finally {
      setDeleting(null);
    }
  };

  const languages = [...new Set(codeFiles.map(f => f.language))];

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
        <h1 className="text-2xl font-bold text-gray-100">Generated Code</h1>
        <p className="text-gray-500">{codeFiles.length} code files generated from your knowledge</p>
      </div>

      {/* Filters */}
      {languages.length > 0 && (
        <div className="flex gap-2 flex-wrap">
          <button
            onClick={() => setFilter('')}
            className={`px-3 py-1 rounded-full text-sm ${
              filter === '' ? 'bg-primary text-black' : 'bg-dark-200 text-gray-400 hover:text-gray-200'
            }`}
          >
            All
          </button>
          {languages.map(lang => (
            <button
              key={lang}
              onClick={() => setFilter(lang)}
              className={`px-3 py-1 rounded-full text-sm ${
                filter === lang ? 'bg-primary text-black' : 'bg-dark-200 text-gray-400 hover:text-gray-200'
              }`}
            >
              {lang}
            </button>
          ))}
        </div>
      )}

      {/* Code Files List */}
      <div className="grid gap-4">
        {codeFiles.map(file => {
          const langColor = LANGUAGE_COLORS[file.language.toLowerCase()] || LANGUAGE_COLORS.default;
          return (
            <div key={file.id} className="bg-dark-100 rounded-xl border border-dark-300 p-6">
              <div className="flex items-start justify-between">
                <div className="flex items-start gap-4">
                  <FileCode className="w-6 h-6 text-primary mt-1" />
                  <div>
                    <h3 className="text-lg font-semibold text-gray-200 font-mono">{file.filename}</h3>
                    <div className="flex items-center gap-3 mt-2">
                      <span className={`px-2 py-1 rounded text-xs ${langColor}`}>
                        {file.language}
                      </span>
                      <span className="text-xs text-gray-500">
                        {file.generation_type}
                      </span>
                      <span className="text-xs text-gray-500">
                        {new Date(file.created_at).toLocaleDateString()}
                      </span>
                    </div>
                    {/* Code Preview */}
                    <pre className="mt-4 p-4 bg-dark-200 rounded-lg text-sm text-gray-300 overflow-x-auto max-h-48 overflow-y-auto">
                      <code>{file.code_content.slice(0, 500)}{file.code_content.length > 500 ? '...' : ''}</code>
                    </pre>
                  </div>
                </div>
                <div className="flex gap-2">
                  <button
                    onClick={() => downloadCode(file.id)}
                    className="btn btn-secondary text-sm"
                    title="Download"
                  >
                    <Download className="w-4 h-4" />
                  </button>
                  <button
                    onClick={() => deleteCode(file.id)}
                    disabled={deleting === file.id}
                    className="btn btn-secondary text-sm"
                    title="Delete"
                  >
                    {deleting === file.id ? (
                      <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-current"></div>
                    ) : (
                      <Trash2 className="w-4 h-4" />
                    )}
                  </button>
                </div>
              </div>
            </div>
          );
        })}
        {codeFiles.length === 0 && (
          <div className="text-center py-12 text-gray-500">
            <Code className="w-12 h-12 mx-auto mb-4 opacity-50" />
            <p>No generated code yet.</p>
            <p className="text-sm mt-2">Use the Code Generation tool to create code from your knowledge base.</p>
          </div>
        )}
      </div>
    </div>
  );
}

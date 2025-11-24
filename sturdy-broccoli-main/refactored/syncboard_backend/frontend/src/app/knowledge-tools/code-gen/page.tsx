'use client';

import { useState } from 'react';
import api from '@/lib/api';
import toast from 'react-hot-toast';
import { Code, Download, Copy, Loader2, Check } from 'lucide-react';

const LANGUAGES = ['python', 'javascript', 'typescript', 'go', 'rust', 'java'];
const PROJECT_TYPES = ['cli', 'api', 'library', 'script', 'web-app'];

export default function CodeGenPage() {
  const [projectType, setProjectType] = useState('');
  const [language, setLanguage] = useState('');
  // Backend returns files as array: [{filename, content, purpose}]
  // We transform it to Record<string, string> for easier rendering
  const [result, setResult] = useState<{
    files?: Record<string, string>;
    concepts_used?: string[];
    setup_instructions?: string | string[];
  } | null>(null);
  const [generating, setGenerating] = useState(false);
  const [copiedFile, setCopiedFile] = useState<string | null>(null);

  const generateCode = async () => {
    setGenerating(true);
    try {
      const data = await api.generateCodeFromKB(projectType || undefined, language || undefined);

      // Transform files array to Record<string, string> if needed
      // Backend returns: [{filename, content, purpose}] or Record<string, string>
      let transformedFiles: Record<string, string> | undefined;
      if (data.files) {
        if (Array.isArray(data.files)) {
          // Transform array format to record format
          transformedFiles = {};
          for (const file of data.files as Array<{ filename: string; content: string; purpose?: string }>) {
            if (file.filename && typeof file.content === 'string') {
              transformedFiles[file.filename] = file.content;
            }
          }
        } else {
          // Already in record format
          transformedFiles = data.files as Record<string, string>;
        }
      }

      // Handle setup_instructions which could be string or array
      const setupInstructions = Array.isArray(data.setup_instructions)
        ? data.setup_instructions.join('\n')
        : data.setup_instructions;

      setResult({
        ...data,
        files: transformedFiles,
        setup_instructions: setupInstructions,
        concepts_used: data.concepts_demonstrated || data.concepts_used,
      });

      if (transformedFiles && Object.keys(transformedFiles).length > 0) {
        toast.success('Code generated successfully!');
      }
    } catch {
      toast.error('Failed to generate code');
    } finally {
      setGenerating(false);
    }
  };

  const copyToClipboard = async (filename: string, content: string) => {
    await navigator.clipboard.writeText(content);
    setCopiedFile(filename);
    setTimeout(() => setCopiedFile(null), 2000);
    toast.success('Copied to clipboard');
  };

  const downloadFile = (filename: string, content: string) => {
    const blob = new Blob([content], { type: 'text/plain' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = filename;
    a.click();
    URL.revokeObjectURL(url);
  };

  return (
    <div className="space-y-6 animate-fadeIn">
      <div>
        <h1 className="text-2xl font-bold text-gray-100">Code Generation</h1>
        <p className="text-gray-500">Generate starter code based on your knowledge base</p>
      </div>

      {/* Controls */}
      <div className="bg-dark-100 rounded-xl border border-dark-300 p-6">
        <div className="grid md:grid-cols-3 gap-4">
          <div>
            <label className="block text-sm text-gray-400 mb-2">Project Type (optional)</label>
            <select
              value={projectType}
              onChange={(e) => setProjectType(e.target.value)}
              className="input w-full"
            >
              <option value="">Auto-detect</option>
              {PROJECT_TYPES.map(type => (
                <option key={type} value={type}>{type}</option>
              ))}
            </select>
          </div>
          <div>
            <label className="block text-sm text-gray-400 mb-2">Language (optional)</label>
            <select
              value={language}
              onChange={(e) => setLanguage(e.target.value)}
              className="input w-full"
            >
              <option value="">Auto-detect</option>
              {LANGUAGES.map(lang => (
                <option key={lang} value={lang}>{lang}</option>
              ))}
            </select>
          </div>
          <div className="flex items-end">
            <button
              onClick={generateCode}
              disabled={generating}
              className="btn btn-primary w-full flex items-center justify-center gap-2"
            >
              {generating ? <Loader2 className="w-4 h-4 animate-spin" /> : <Code className="w-4 h-4" />}
              {generating ? 'Generating...' : 'Generate Code'}
            </button>
          </div>
        </div>
      </div>

      {/* Results */}
      {result && (
        <div className="space-y-6">
          {/* Concepts Used */}
          {result.concepts_used && result.concepts_used.length > 0 && (
            <div className="bg-dark-100 rounded-xl border border-dark-300 p-6">
              <h2 className="text-lg font-semibold text-gray-200 mb-4">Concepts Used</h2>
              <div className="flex flex-wrap gap-2">
                {result.concepts_used.map((concept, i) => (
                  <span key={i} className="px-3 py-1 bg-primary/10 text-primary rounded-full text-sm">
                    {concept}
                  </span>
                ))}
              </div>
            </div>
          )}

          {/* Generated Files */}
          {result.files && Object.keys(result.files).length > 0 && (
            <div className="space-y-4">
              <h2 className="text-lg font-semibold text-gray-200">Generated Files</h2>
              {Object.entries(result.files).map(([filename, content]) => (
                <div key={filename} className="bg-dark-100 rounded-xl border border-dark-300 overflow-hidden">
                  <div className="flex items-center justify-between p-4 border-b border-dark-300">
                    <span className="font-mono text-primary">{filename}</span>
                    <div className="flex gap-2">
                      <button
                        onClick={() => copyToClipboard(filename, content)}
                        className="btn btn-secondary text-sm"
                      >
                        {copiedFile === filename ? <Check className="w-4 h-4" /> : <Copy className="w-4 h-4" />}
                      </button>
                      <button
                        onClick={() => downloadFile(filename, content)}
                        className="btn btn-secondary text-sm"
                      >
                        <Download className="w-4 h-4" />
                      </button>
                    </div>
                  </div>
                  <pre className="p-4 text-sm text-gray-300 overflow-x-auto max-h-96">
                    <code>{content}</code>
                  </pre>
                </div>
              ))}
            </div>
          )}

          {/* Setup Instructions */}
          {result.setup_instructions && (
            <div className="bg-dark-100 rounded-xl border border-dark-300 p-6">
              <h2 className="text-lg font-semibold text-gray-200 mb-4">Setup Instructions</h2>
              <pre className="text-sm text-gray-300 whitespace-pre-wrap">{result.setup_instructions}</pre>
            </div>
          )}
        </div>
      )}

      {!result && !generating && (
        <div className="text-center py-12 text-gray-500">
          <Code className="w-12 h-12 mx-auto mb-4 opacity-50" />
          <p>Generate starter code based on your knowledge base concepts</p>
        </div>
      )}
    </div>
  );
}

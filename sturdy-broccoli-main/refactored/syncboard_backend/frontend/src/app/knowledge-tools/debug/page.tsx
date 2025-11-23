'use client';

import { useState } from 'react';
import api from '@/lib/api';
import toast from 'react-hot-toast';
import { Bug, AlertCircle, CheckCircle, Lightbulb, FileText, Code, Loader2 } from 'lucide-react';
import type { DebugResult } from '@/types/api';

export default function DebugPage() {
  const [errorMessage, setErrorMessage] = useState('');
  const [codeSnippet, setCodeSnippet] = useState('');
  const [context, setContext] = useState('');
  const [result, setResult] = useState<DebugResult | null>(null);
  const [loading, setLoading] = useState(false);

  const debugError = async () => {
    if (!errorMessage.trim()) {
      toast.error('Please enter an error message');
      return;
    }
    setLoading(true);
    try {
      const data = await api.debugError(errorMessage, codeSnippet || undefined, context || undefined);
      setResult(data);
    } catch {
      toast.error('Failed to analyze error');
    } finally {
      setLoading(false);
    }
  };

  const getConfidenceColor = (confidence: number) => {
    if (confidence >= 0.8) return 'text-green-400';
    if (confidence >= 0.6) return 'text-yellow-400';
    return 'text-orange-400';
  };

  return (
    <div className="space-y-6 animate-fadeIn">
      <div>
        <h1 className="text-2xl font-bold text-gray-100">Debug Assistant</h1>
        <p className="text-gray-500">Get help debugging errors using your knowledge base</p>
      </div>

      {/* Input Form */}
      <div className="bg-dark-100 rounded-xl border border-dark-300 p-6 space-y-4">
        <div>
          <label className="block text-sm text-gray-400 mb-2">Error Message *</label>
          <textarea
            value={errorMessage}
            onChange={(e) => setErrorMessage(e.target.value)}
            placeholder="Paste the error message here..."
            className="input w-full font-mono text-sm"
            rows={3}
          />
        </div>

        <div>
          <label className="block text-sm text-gray-400 mb-2">Code Snippet (optional)</label>
          <textarea
            value={codeSnippet}
            onChange={(e) => setCodeSnippet(e.target.value)}
            placeholder="Paste the relevant code snippet..."
            className="input w-full font-mono text-sm"
            rows={6}
          />
        </div>

        <div>
          <label className="block text-sm text-gray-400 mb-2">Additional Context (optional)</label>
          <input
            type="text"
            value={context}
            onChange={(e) => setContext(e.target.value)}
            placeholder="E.g., Using React 18 with TypeScript..."
            className="input w-full"
          />
        </div>

        <button
          onClick={debugError}
          disabled={loading}
          className="btn btn-primary flex items-center gap-2"
        >
          {loading ? <Loader2 className="w-4 h-4 animate-spin" /> : <Bug className="w-4 h-4" />}
          Analyze Error
        </button>
      </div>

      {/* Results */}
      {result && (
        <div className="space-y-6">
          {/* Confidence */}
          <div className="flex items-center gap-2">
            <span className="text-gray-500">Confidence:</span>
            <span className={`font-semibold ${getConfidenceColor(result.confidence)}`}>
              {Math.round(result.confidence * 100)}%
            </span>
          </div>

          {/* Likely Cause */}
          <div className="bg-red-400/5 border border-red-400/20 rounded-xl p-6">
            <div className="flex items-center gap-2 mb-4">
              <AlertCircle className="w-5 h-5 text-red-400" />
              <h2 className="text-lg font-semibold text-gray-200">Likely Cause</h2>
            </div>
            <p className="text-gray-300">{result.likely_cause}</p>
          </div>

          {/* Explanation */}
          <div className="bg-dark-100 rounded-xl border border-dark-300 p-6">
            <div className="flex items-center gap-2 mb-4">
              <Lightbulb className="w-5 h-5 text-yellow-400" />
              <h2 className="text-lg font-semibold text-gray-200">Explanation</h2>
            </div>
            <p className="text-gray-300">{result.explanation}</p>
          </div>

          {/* Step-by-Step Fix */}
          {result.step_by_step_fix.length > 0 && (
            <div className="bg-dark-100 rounded-xl border border-dark-300 p-6">
              <div className="flex items-center gap-2 mb-4">
                <CheckCircle className="w-5 h-5 text-green-400" />
                <h2 className="text-lg font-semibold text-gray-200">Step-by-Step Fix</h2>
              </div>
              <ol className="space-y-3">
                {result.step_by_step_fix.map((step, i) => (
                  <li key={i} className="flex items-start gap-3">
                    <span className="flex-shrink-0 w-6 h-6 rounded-full bg-green-400/20 text-green-400 text-sm flex items-center justify-center">
                      {i + 1}
                    </span>
                    <span className="text-gray-300">{step}</span>
                  </li>
                ))}
              </ol>
            </div>
          )}

          {/* Code Suggestion */}
          {result.code_suggestion && (
            <div className="bg-dark-100 rounded-xl border border-dark-300 overflow-hidden">
              <div className="flex items-center gap-2 p-4 border-b border-dark-300">
                <Code className="w-5 h-5 text-primary" />
                <h2 className="text-lg font-semibold text-gray-200">Suggested Fix</h2>
              </div>
              <pre className="p-4 text-sm text-gray-300 overflow-x-auto">
                <code>{result.code_suggestion}</code>
              </pre>
            </div>
          )}

          {/* Prevention Tips */}
          {result.prevention_tips.length > 0 && (
            <div className="bg-dark-100 rounded-xl border border-dark-300 p-6">
              <h2 className="text-lg font-semibold text-gray-200 mb-4">Prevention Tips</h2>
              <ul className="space-y-2">
                {result.prevention_tips.map((tip, i) => (
                  <li key={i} className="text-gray-400 text-sm flex items-start gap-2">
                    <span className="text-primary">•</span> {tip}
                  </li>
                ))}
              </ul>
            </div>
          )}

          {/* Related Docs */}
          {result.related_docs.length > 0 && (
            <div className="bg-dark-100 rounded-xl border border-dark-300 p-6">
              <div className="flex items-center gap-2 mb-4">
                <FileText className="w-5 h-5 text-gray-400" />
                <h2 className="text-lg font-semibold text-gray-200">Related Documents</h2>
              </div>
              <div className="flex flex-wrap gap-2">
                {result.related_docs.map((doc, i) => (
                  <span key={i} className="px-3 py-1 bg-dark-200 text-gray-400 rounded text-sm">
                    {doc.title || `Document ${doc.doc_id}`}
                  </span>
                ))}
              </div>
            </div>
          )}
        </div>
      )}

      {!result && !loading && (
        <div className="text-center py-12 text-gray-500">
          <Bug className="w-12 h-12 mx-auto mb-4 opacity-50" />
          <p>Paste an error message to get debugging help</p>
        </div>
      )}
    </div>
  );
}

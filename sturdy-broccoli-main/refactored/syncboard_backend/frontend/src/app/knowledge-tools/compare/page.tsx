'use client';

import { useEffect, useState } from 'react';
import api from '@/lib/api';
import toast from 'react-hot-toast';
import { GitCompare, CheckCircle, AlertTriangle, Lightbulb, Loader2 } from 'lucide-react';
import type { Document, DocumentComparison } from '@/types/api';

export default function ComparePage() {
  const [documents, setDocuments] = useState<Document[]>([]);
  const [docA, setDocA] = useState<number | null>(null);
  const [docB, setDocB] = useState<number | null>(null);
  const [comparison, setComparison] = useState<DocumentComparison | null>(null);
  const [loading, setLoading] = useState(true);
  const [comparing, setComparing] = useState(false);

  useEffect(() => { loadDocuments(); }, []);

  const loadDocuments = async () => {
    try {
      const data = await api.getDocuments();
      setDocuments(data.documents);
    } catch {
      toast.error('Failed to load documents');
    } finally {
      setLoading(false);
    }
  };

  const compareDocuments = async () => {
    if (!docA || !docB) {
      toast.error('Please select two documents');
      return;
    }
    if (docA === docB) {
      toast.error('Please select different documents');
      return;
    }
    setComparing(true);
    try {
      const data = await api.compareDocuments(docA, docB);
      setComparison(data);
    } catch {
      toast.error('Failed to compare documents');
    } finally {
      setComparing(false);
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
        <h1 className="text-2xl font-bold text-gray-100">Compare Documents</h1>
        <p className="text-gray-500">Compare two documents for overlaps, contradictions, and insights</p>
      </div>

      {/* Document Selection */}
      <div className="bg-dark-100 rounded-xl border border-dark-300 p-6">
        <div className="grid md:grid-cols-3 gap-4 items-end">
          <div>
            <label className="block text-sm text-gray-400 mb-2">Document A</label>
            <select
              value={docA || ''}
              onChange={(e) => setDocA(Number(e.target.value))}
              className="input w-full"
            >
              <option value="">Select first document...</option>
              {documents.map(doc => (
                <option key={doc.id} value={doc.id} disabled={doc.id === docB}>
                  {doc.title}
                </option>
              ))}
            </select>
          </div>
          <div>
            <label className="block text-sm text-gray-400 mb-2">Document B</label>
            <select
              value={docB || ''}
              onChange={(e) => setDocB(Number(e.target.value))}
              className="input w-full"
            >
              <option value="">Select second document...</option>
              {documents.map(doc => (
                <option key={doc.id} value={doc.id} disabled={doc.id === docA}>
                  {doc.title}
                </option>
              ))}
            </select>
          </div>
          <button
            onClick={compareDocuments}
            disabled={comparing || !docA || !docB}
            className="btn btn-primary flex items-center justify-center gap-2"
          >
            {comparing ? <Loader2 className="w-4 h-4 animate-spin" /> : <GitCompare className="w-4 h-4" />}
            Compare
          </button>
        </div>
      </div>

      {/* Comparison Results */}
      {comparison && (
        <div className="space-y-6">
          {/* Overlapping Concepts */}
          {comparison.overlapping_concepts.length > 0 && (
            <div className="bg-dark-100 rounded-xl border border-dark-300 p-6">
              <div className="flex items-center gap-2 mb-4">
                <CheckCircle className="w-5 h-5 text-green-400" />
                <h2 className="text-lg font-semibold text-gray-200">Overlapping Concepts</h2>
              </div>
              <div className="flex flex-wrap gap-2">
                {comparison.overlapping_concepts.map((concept, i) => (
                  <span key={i} className="px-3 py-1 bg-green-400/10 text-green-400 rounded-full text-sm">
                    {concept}
                  </span>
                ))}
              </div>
            </div>
          )}

          {/* Contradictions */}
          {comparison.contradictions.length > 0 && (
            <div className="bg-dark-100 rounded-xl border border-dark-300 p-6">
              <div className="flex items-center gap-2 mb-4">
                <AlertTriangle className="w-5 h-5 text-red-400" />
                <h2 className="text-lg font-semibold text-gray-200">Contradictions</h2>
              </div>
              <ul className="space-y-3">
                {comparison.contradictions.map((item, i) => {
                  // Handle both string and object formats
                  if (typeof item === 'string') {
                    return (
                      <li key={i} className="text-gray-300 text-sm p-3 bg-red-400/5 border border-red-400/20 rounded">
                        {item}
                      </li>
                    );
                  }
                  const c = item as { topic?: string; doc_a_says?: string; doc_b_says?: string; resolution?: string };
                  return (
                    <li key={i} className="p-3 bg-red-400/5 border border-red-400/20 rounded space-y-2">
                      {c.topic && <p className="font-medium text-red-400">{c.topic}</p>}
                      {c.doc_a_says && <p className="text-sm text-gray-400">Doc A: {c.doc_a_says}</p>}
                      {c.doc_b_says && <p className="text-sm text-gray-400">Doc B: {c.doc_b_says}</p>}
                      {c.resolution && <p className="text-sm text-gray-300 mt-1">Resolution: {c.resolution}</p>}
                    </li>
                  );
                })}
              </ul>
            </div>
          )}

          {/* Complementary Info */}
          {comparison.complementary_info.length > 0 && (
            <div className="bg-dark-100 rounded-xl border border-dark-300 p-6">
              <div className="flex items-center gap-2 mb-4">
                <Lightbulb className="w-5 h-5 text-yellow-400" />
                <h2 className="text-lg font-semibold text-gray-200">Complementary Information</h2>
              </div>
              <ul className="space-y-3">
                {comparison.complementary_info.map((item, i) => {
                  // Handle both string and object formats
                  if (typeof item === 'string') {
                    return (
                      <li key={i} className="text-gray-300 text-sm flex items-start gap-2">
                        <span className="text-yellow-400">+</span> {item}
                      </li>
                    );
                  }
                  const c = item as { doc_a_has?: string; doc_b_has?: string; combined_value?: string };
                  return (
                    <li key={i} className="p-3 bg-yellow-400/5 border border-yellow-400/20 rounded space-y-1">
                      {c.doc_a_has && <p className="text-sm text-gray-400">Doc A has: {c.doc_a_has}</p>}
                      {c.doc_b_has && <p className="text-sm text-gray-400">Doc B has: {c.doc_b_has}</p>}
                      {c.combined_value && <p className="text-sm text-gray-300 mt-1">Combined: {c.combined_value}</p>}
                    </li>
                  );
                })}
              </ul>
            </div>
          )}

          {/* Recommendations */}
          <div className="grid md:grid-cols-2 gap-4">
            {comparison.more_authoritative && (
              <div className="bg-dark-100 rounded-xl border border-dark-300 p-6">
                <p className="text-sm text-gray-500 mb-2">More Authoritative</p>
                <p className="text-gray-200">{comparison.more_authoritative}</p>
              </div>
            )}
            {comparison.recommended_order && (
              <div className="bg-dark-100 rounded-xl border border-dark-300 p-6">
                <p className="text-sm text-gray-500 mb-2">Recommended Reading Order</p>
                <p className="text-gray-200">{comparison.recommended_order}</p>
              </div>
            )}
          </div>

          {/* Synthesis */}
          {comparison.synthesis && (
            <div className="bg-primary/10 border border-primary/30 rounded-xl p-6">
              <h2 className="text-lg font-semibold text-gray-200 mb-4">Synthesis</h2>
              <p className="text-gray-300">{comparison.synthesis}</p>
            </div>
          )}
        </div>
      )}

      {!comparison && !comparing && (
        <div className="text-center py-12 text-gray-500">
          <GitCompare className="w-12 h-12 mx-auto mb-4 opacity-50" />
          <p>Select two documents to compare</p>
        </div>
      )}
    </div>
  );
}

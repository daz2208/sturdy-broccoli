'use client';

import { useEffect, useState } from 'react';
import api from '@/lib/api';
import toast from 'react-hot-toast';
import { Award, FileText, AlertCircle, CheckCircle, Loader2 } from 'lucide-react';
import type { Document } from '@/types/api';

interface QualityScore {
  information_density: number;
  actionability: number;
  currency: number;
  uniqueness: number;
  overall: number;
}

interface QualityResult {
  doc_id: number;
  scores: QualityScore;
  key_excerpts: string[];
  sections_to_skip: string[];
  missing_context: string[];
}

export default function QualityPage() {
  const [documents, setDocuments] = useState<Document[]>([]);
  const [selectedDoc, setSelectedDoc] = useState<number | null>(null);
  const [result, setResult] = useState<QualityResult | null>(null);
  const [loading, setLoading] = useState(true);
  const [analyzing, setAnalyzing] = useState(false);

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

  const analyzeQuality = async () => {
    if (!selectedDoc) {
      toast.error('Please select a document');
      return;
    }
    setAnalyzing(true);
    try {
      const data = await api.scoreDocumentQuality(selectedDoc);
      setResult(data);
    } catch {
      toast.error('Failed to analyze document quality');
    } finally {
      setAnalyzing(false);
    }
  };

  // Backend returns scores as 1-10, normalize to 0-1 for percentage display
  const normalizeScore = (score: number) => score / 10;

  const getScoreColor = (score: number) => {
    const normalized = normalizeScore(score);
    if (normalized >= 0.8) return 'text-green-400';
    if (normalized >= 0.6) return 'text-yellow-400';
    if (normalized >= 0.4) return 'text-orange-400';
    return 'text-red-400';
  };

  const getScoreBar = (score: number) => {
    const percentage = normalizeScore(score) * 100;
    const normalized = normalizeScore(score);
    let bgColor = 'bg-red-400';
    if (normalized >= 0.8) bgColor = 'bg-green-400';
    else if (normalized >= 0.6) bgColor = 'bg-yellow-400';
    else if (normalized >= 0.4) bgColor = 'bg-orange-400';

    return (
      <div className="w-full h-2 bg-dark-300 rounded-full overflow-hidden">
        <div className={`h-full ${bgColor}`} style={{ width: `${percentage}%` }} />
      </div>
    );
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
        <h1 className="text-2xl font-bold text-gray-100">Document Quality</h1>
        <p className="text-gray-500">Score and analyze document quality</p>
      </div>

      {/* Controls */}
      <div className="bg-dark-100 rounded-xl border border-dark-300 p-6">
        <div className="flex gap-4">
          <div className="flex-1">
            <label className="block text-sm text-gray-400 mb-2">Select Document</label>
            <select
              value={selectedDoc || ''}
              onChange={(e) => setSelectedDoc(Number(e.target.value))}
              className="input w-full"
            >
              <option value="">Choose a document...</option>
              {documents.map(doc => (
                <option key={doc.id} value={doc.id}>{doc.title}</option>
              ))}
            </select>
          </div>
          <div className="flex items-end">
            <button
              onClick={analyzeQuality}
              disabled={analyzing || !selectedDoc}
              className="btn btn-primary flex items-center gap-2"
            >
              {analyzing ? <Loader2 className="w-4 h-4 animate-spin" /> : <Award className="w-4 h-4" />}
              Analyze
            </button>
          </div>
        </div>
      </div>

      {/* Results */}
      {result && (
        <div className="space-y-6">
          {/* Overall Score */}
          <div className="bg-dark-100 rounded-xl border border-dark-300 p-6 text-center">
            <p className="text-gray-500 mb-2">Overall Quality Score</p>
            <p className={`text-5xl font-bold ${getScoreColor(result.scores.overall)}`}>
              {Math.round(normalizeScore(result.scores.overall) * 100)}%
            </p>
          </div>

          {/* Score Breakdown */}
          <div className="bg-dark-100 rounded-xl border border-dark-300 p-6">
            <h2 className="text-lg font-semibold text-gray-200 mb-4">Score Breakdown</h2>
            <div className="space-y-4">
              {[
                { label: 'Information Density', value: result.scores.information_density },
                { label: 'Actionability', value: result.scores.actionability },
                { label: 'Currency', value: result.scores.currency },
                { label: 'Uniqueness', value: result.scores.uniqueness },
              ].map(({ label, value }) => (
                <div key={label}>
                  <div className="flex justify-between text-sm mb-1">
                    <span className="text-gray-400">{label}</span>
                    <span className={getScoreColor(value)}>{Math.round(normalizeScore(value) * 100)}%</span>
                  </div>
                  {getScoreBar(value)}
                </div>
              ))}
            </div>
          </div>

          {/* Key Excerpts */}
          {result.key_excerpts.length > 0 && (
            <div className="bg-dark-100 rounded-xl border border-dark-300 p-6">
              <div className="flex items-center gap-2 mb-4">
                <CheckCircle className="w-5 h-5 text-green-400" />
                <h2 className="text-lg font-semibold text-gray-200">Key Excerpts</h2>
              </div>
              <ul className="space-y-2">
                {result.key_excerpts.map((excerpt, i) => (
                  <li key={i} className="text-gray-300 text-sm p-3 bg-dark-200 rounded">
                    &quot;{excerpt}&quot;
                  </li>
                ))}
              </ul>
            </div>
          )}

          {/* Sections to Skip */}
          {result.sections_to_skip.length > 0 && (
            <div className="bg-dark-100 rounded-xl border border-dark-300 p-6">
              <div className="flex items-center gap-2 mb-4">
                <AlertCircle className="w-5 h-5 text-yellow-400" />
                <h2 className="text-lg font-semibold text-gray-200">Sections to Skip</h2>
              </div>
              <ul className="space-y-2">
                {result.sections_to_skip.map((section, i) => (
                  <li key={i} className="text-gray-400 text-sm flex items-start gap-2">
                    <span className="text-yellow-400">•</span> {section}
                  </li>
                ))}
              </ul>
            </div>
          )}

          {/* Missing Context */}
          {result.missing_context.length > 0 && (
            <div className="bg-dark-100 rounded-xl border border-dark-300 p-6">
              <div className="flex items-center gap-2 mb-4">
                <AlertCircle className="w-5 h-5 text-orange-400" />
                <h2 className="text-lg font-semibold text-gray-200">Missing Context</h2>
              </div>
              <ul className="space-y-2">
                {result.missing_context.map((item, i) => (
                  <li key={i} className="text-gray-400 text-sm flex items-start gap-2">
                    <span className="text-orange-400">•</span> {item}
                  </li>
                ))}
              </ul>
            </div>
          )}
        </div>
      )}

      {!result && !analyzing && (
        <div className="text-center py-12 text-gray-500">
          <Award className="w-12 h-12 mx-auto mb-4 opacity-50" />
          <p>Select a document to analyze its quality</p>
        </div>
      )}
    </div>
  );
}

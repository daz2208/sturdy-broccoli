'use client';

import { useEffect, useState } from 'react';
import api from '@/lib/api';
import toast from 'react-hot-toast';
import { Target, AlertTriangle, TrendingUp, BookOpen, RefreshCw } from 'lucide-react';
import type { GapAnalysisResponse, KnowledgeGap } from '@/types/api';

const SEVERITY_COLORS = {
  critical: 'text-red-400 bg-red-400/10 border-red-400/30',
  high: 'text-orange-400 bg-orange-400/10 border-orange-400/30',
  medium: 'text-yellow-400 bg-yellow-400/10 border-yellow-400/30',
  low: 'text-green-400 bg-green-400/10 border-green-400/30',
};

export default function GapAnalysisPage() {
  const [analysis, setAnalysis] = useState<GapAnalysisResponse | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => { loadAnalysis(); }, []);

  const loadAnalysis = async () => {
    setLoading(true);
    try {
      const data = await api.analyzeKnowledgeGaps();
      setAnalysis(data);
    } catch {
      toast.error('Failed to analyze knowledge gaps');
    } finally {
      setLoading(false);
    }
  };

  if (loading) {
    return (
      <div className="flex flex-col items-center justify-center py-12">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary mb-4"></div>
        <p className="text-gray-500">Analyzing your knowledge base...</p>
      </div>
    );
  }

  if (!analysis) {
    return (
      <div className="text-center py-12 text-gray-500">
        <AlertTriangle className="w-12 h-12 mx-auto mb-4 opacity-50" />
        <p>Could not load gap analysis. Try again later.</p>
      </div>
    );
  }

  return (
    <div className="space-y-6 animate-fadeIn">
      <div className="flex justify-between items-center">
        <div>
          <h1 className="text-2xl font-bold text-gray-100">Knowledge Gap Analysis</h1>
          <p className="text-gray-500">Identify gaps and opportunities in your knowledge base</p>
        </div>
        <button onClick={loadAnalysis} className="btn btn-secondary flex items-center gap-2">
          <RefreshCw className="w-4 h-4" /> Refresh
        </button>
      </div>

      {/* Summary Stats */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <div className="bg-dark-100 rounded-xl border border-dark-300 p-4">
          <p className="text-gray-500 text-sm">Documents</p>
          <p className="text-2xl font-bold text-gray-100">{analysis.total_documents}</p>
        </div>
        <div className="bg-dark-100 rounded-xl border border-dark-300 p-4">
          <p className="text-gray-500 text-sm">Concepts</p>
          <p className="text-2xl font-bold text-primary">{analysis.total_concepts}</p>
        </div>
        <div className="bg-dark-100 rounded-xl border border-dark-300 p-4">
          <p className="text-gray-500 text-sm">Gaps Found</p>
          <p className="text-2xl font-bold text-yellow-400">{analysis.gaps.length}</p>
        </div>
        <div className="bg-dark-100 rounded-xl border border-dark-300 p-4">
          <p className="text-gray-500 text-sm">Shallow Areas</p>
          <p className="text-2xl font-bold text-orange-400">{analysis.shallow_areas.length}</p>
        </div>
      </div>

      {/* Inferred Goal */}
      {analysis.inferred_goal && (
        <div className="bg-primary/10 border border-primary/30 rounded-xl p-4">
          <div className="flex items-center gap-2 mb-2">
            <Target className="w-5 h-5 text-primary" />
            <span className="font-semibold text-gray-200">Inferred Goal</span>
          </div>
          <p className="text-gray-300">{analysis.inferred_goal}</p>
        </div>
      )}

      {/* Strongest Areas */}
      {analysis.strongest_areas.length > 0 && (
        <div className="bg-dark-100 rounded-xl border border-dark-300 p-6">
          <div className="flex items-center gap-2 mb-4">
            <TrendingUp className="w-5 h-5 text-green-400" />
            <h2 className="text-lg font-semibold text-gray-200">Strongest Areas</h2>
          </div>
          <div className="flex flex-wrap gap-2">
            {analysis.strongest_areas.map((area, i) => (
              <span key={i} className="px-3 py-1 bg-green-400/10 text-green-400 rounded-full text-sm">
                {area}
              </span>
            ))}
          </div>
        </div>
      )}

      {/* Knowledge Gaps */}
      {analysis.gaps.length > 0 && (
        <div className="bg-dark-100 rounded-xl border border-dark-300 p-6">
          <div className="flex items-center gap-2 mb-4">
            <AlertTriangle className="w-5 h-5 text-yellow-400" />
            <h2 className="text-lg font-semibold text-gray-200">Knowledge Gaps</h2>
          </div>
          <div className="space-y-4">
            {analysis.gaps.map((gap, i) => (
              <div key={i} className={`p-4 rounded-lg border ${SEVERITY_COLORS[gap.severity]}`}>
                <div className="flex items-start justify-between">
                  <div>
                    <h3 className="font-semibold">{gap.area}</h3>
                    <p className="text-sm text-gray-400 mt-1">{gap.description}</p>
                  </div>
                  <span className="text-xs uppercase font-medium">{gap.severity}</span>
                </div>
                {gap.suggested_topics.length > 0 && (
                  <div className="mt-3">
                    <p className="text-xs text-gray-500 mb-2">Suggested topics to learn:</p>
                    <div className="flex flex-wrap gap-1">
                      {gap.suggested_topics.map((topic, j) => (
                        <span key={j} className="px-2 py-0.5 bg-dark-200 rounded text-xs text-gray-300">
                          {topic}
                        </span>
                      ))}
                    </div>
                  </div>
                )}
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Recommended Learning Path */}
      {analysis.recommended_learning_path.length > 0 && (
        <div className="bg-dark-100 rounded-xl border border-dark-300 p-6">
          <div className="flex items-center gap-2 mb-4">
            <BookOpen className="w-5 h-5 text-primary" />
            <h2 className="text-lg font-semibold text-gray-200">Recommended Learning Path</h2>
          </div>
          <ol className="space-y-2">
            {analysis.recommended_learning_path.map((step, i) => (
              <li key={i} className="flex items-start gap-3">
                <span className="flex-shrink-0 w-6 h-6 rounded-full bg-primary/20 text-primary text-sm flex items-center justify-center">
                  {i + 1}
                </span>
                <span className="text-gray-300">{step}</span>
              </li>
            ))}
          </ol>
        </div>
      )}
    </div>
  );
}

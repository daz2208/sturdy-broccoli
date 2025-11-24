'use client';

import { useState } from 'react';
import api from '@/lib/api';
import toast from 'react-hot-toast';
import { Route, Clock, FileText, ExternalLink, Loader2 } from 'lucide-react';
import type { LearningPath } from '@/types/api';

export default function LearningPathPage() {
  const [goal, setGoal] = useState('');
  const [path, setPath] = useState<LearningPath | null>(null);
  const [loading, setLoading] = useState(false);

  const generatePath = async () => {
    if (!goal.trim()) {
      toast.error('Please enter a learning goal');
      return;
    }
    setLoading(true);
    try {
      const data = await api.optimizeLearningPath(goal);
      setPath(data);
    } catch {
      toast.error('Failed to generate learning path');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="space-y-6 animate-fadeIn">
      <div>
        <h1 className="text-2xl font-bold text-gray-100">Learning Path</h1>
        <p className="text-gray-500">Get an optimized learning path for your goal</p>
      </div>

      {/* Goal Input */}
      <div className="bg-dark-100 rounded-xl border border-dark-300 p-6">
        <label className="block text-sm text-gray-400 mb-2">What do you want to learn?</label>
        <div className="flex gap-3">
          <input
            type="text"
            value={goal}
            onChange={(e) => setGoal(e.target.value)}
            placeholder="E.g., Master React hooks, Learn Kubernetes, Understand machine learning"
            className="input flex-1"
            onKeyPress={(e) => e.key === 'Enter' && generatePath()}
          />
          <button
            onClick={generatePath}
            disabled={loading}
            className="btn btn-primary flex items-center gap-2"
          >
            {loading ? <Loader2 className="w-4 h-4 animate-spin" /> : <Route className="w-4 h-4" />}
            Generate
          </button>
        </div>
      </div>

      {/* Learning Path Display */}
      {path && (
        <div className="space-y-6">
          {/* Summary */}
          <div className="bg-primary/10 border border-primary/30 rounded-xl p-6">
            <h2 className="text-lg font-semibold text-gray-200 mb-2">Learning Path: {path.goal}</h2>
            <div className="flex items-center gap-6 text-gray-400">
              <span className="flex items-center gap-2">
                <FileText className="w-4 h-4" />
                {path.total_documents} documents
              </span>
              <span className="flex items-center gap-2">
                <Clock className="w-4 h-4" />
                ~{path.estimated_hours} hours
              </span>
            </div>
          </div>

          {/* Ordered Documents */}
          <div className="bg-dark-100 rounded-xl border border-dark-300 p-6">
            <h2 className="text-lg font-semibold text-gray-200 mb-4">Recommended Order</h2>
            <div className="space-y-4">
              {path.ordered_docs.map((doc, i) => {
                // Handle both frontend field names and backend field names
                const reason = doc.reason || doc.why_this_order;
                const timeEstimate = doc.time_estimate || (doc.time_estimate_minutes ? `${doc.time_estimate_minutes} min` : null);
                return (
                  <div key={doc.doc_id || i} className="flex items-start gap-4 p-4 bg-dark-200 rounded-lg">
                    <div className="flex-shrink-0 w-8 h-8 rounded-full bg-primary/20 text-primary flex items-center justify-center font-semibold">
                      {i + 1}
                    </div>
                    <div className="flex-1">
                      <h3 className="font-semibold text-gray-200">{doc.title}</h3>
                      {reason && <p className="text-sm text-gray-400 mt-1">{reason}</p>}
                      {timeEstimate && (
                        <span className="inline-flex items-center gap-1 text-xs text-gray-500 mt-2">
                          <Clock className="w-3 h-3" /> {timeEstimate}
                        </span>
                      )}
                    </div>
                  </div>
                );
              })}
            </div>
          </div>

          {/* Skip List */}
          {path.skip_list.length > 0 && (
            <div className="bg-dark-100 rounded-xl border border-dark-300 p-6">
              <h2 className="text-lg font-semibold text-gray-200 mb-4">Can Skip (Already Know)</h2>
              <div className="flex flex-wrap gap-2">
                {path.skip_list.map((item, i) => (
                  <span key={i} className="px-3 py-1 bg-dark-200 text-gray-400 rounded-full text-sm">
                    {item}
                  </span>
                ))}
              </div>
            </div>
          )}

          {/* External Resources */}
          {path.external_resources.length > 0 && (
            <div className="bg-dark-100 rounded-xl border border-dark-300 p-6">
              <h2 className="text-lg font-semibold text-gray-200 mb-4">Recommended External Resources</h2>
              <ul className="space-y-2">
                {path.external_resources.map((resource, i) => (
                  <li key={i} className="flex items-center gap-2 text-gray-300">
                    <ExternalLink className="w-4 h-4 text-primary" />
                    {resource}
                  </li>
                ))}
              </ul>
            </div>
          )}
        </div>
      )}

      {!path && !loading && (
        <div className="text-center py-12 text-gray-500">
          <Route className="w-12 h-12 mx-auto mb-4 opacity-50" />
          <p>Enter a learning goal to generate your personalized path</p>
        </div>
      )}
    </div>
  );
}

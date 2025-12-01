'use client';

import { useEffect, useState, useCallback } from 'react';
import api from '@/lib/api';
import toast from 'react-hot-toast';
import { Calendar, FileText, Lightbulb, TrendingUp, RefreshCw } from 'lucide-react';
import type { WeeklyDigest } from '@/types/api';

export default function DigestPage() {
  const [digest, setDigest] = useState<WeeklyDigest | null>(null);
  const [loading, setLoading] = useState(true);
  const [days, setDays] = useState(7);

  const loadDigest = useCallback(async () => {
    setLoading(true);
    try {
      const data = await api.getWeeklyDigest(days);
      setDigest(data);
    } catch {
      toast.error('Failed to load digest');
    } finally {
      setLoading(false);
    }
  }, [days]);

  useEffect(() => {
    loadDigest();
  }, [loadDigest]);

  if (loading) {
    return (
      <div className="flex flex-col items-center justify-center py-12">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary mb-4"></div>
        <p className="text-gray-500">Generating your digest...</p>
      </div>
    );
  }

  if (!digest) {
    return (
      <div className="text-center py-12 text-gray-500">
        <Calendar className="w-12 h-12 mx-auto mb-4 opacity-50" />
        <p>Could not generate digest. Try again later.</p>
      </div>
    );
  }

  return (
    <div className="space-y-6 animate-fadeIn">
      <div className="flex justify-between items-center">
        <div>
          <h1 className="text-2xl font-bold text-gray-100">Weekly Digest</h1>
          <p className="text-gray-500">
            {new Date(digest.period_start).toLocaleDateString()} - {new Date(digest.period_end).toLocaleDateString()}
          </p>
        </div>
        <div className="flex items-center gap-3">
          <select
            value={days}
            onChange={(e) => setDays(Number(e.target.value))}
            className="input"
          >
            <option value={7}>Last 7 days</option>
            <option value={14}>Last 14 days</option>
            <option value={30}>Last 30 days</option>
          </select>
          <button onClick={loadDigest} className="btn btn-secondary">
            <RefreshCw className="w-4 h-4" />
          </button>
        </div>
      </div>

      {/* Stats */}
      <div className="bg-dark-100 rounded-xl border border-dark-300 p-6">
        <div className="flex items-center gap-2 mb-4">
          <FileText className="w-5 h-5 text-primary" />
          <span className="font-semibold text-gray-200">Activity Summary</span>
        </div>
        <p className="text-3xl font-bold text-primary">{digest.documents_added}</p>
        <p className="text-gray-500">documents added</p>
      </div>

      {/* Executive Summary */}
      <div className="bg-dark-100 rounded-xl border border-dark-300 p-6">
        <h2 className="text-lg font-semibold text-gray-200 mb-4">Executive Summary</h2>
        <p className="text-gray-300 leading-relaxed">{digest.executive_summary}</p>
      </div>

      <div className="grid md:grid-cols-2 gap-6">
        {/* New Concepts */}
        {digest.new_concepts.length > 0 && (
          <div className="bg-dark-100 rounded-xl border border-dark-300 p-6">
            <div className="flex items-center gap-2 mb-4">
              <Lightbulb className="w-5 h-5 text-yellow-400" />
              <h2 className="text-lg font-semibold text-gray-200">New Concepts</h2>
            </div>
            <div className="flex flex-wrap gap-2">
              {digest.new_concepts.map((concept, i) => (
                <span key={i} className="px-3 py-1 bg-yellow-400/10 text-yellow-400 rounded-full text-sm">
                  {concept}
                </span>
              ))}
            </div>
          </div>
        )}

        {/* Skills Improved */}
        {digest.skills_improved.length > 0 && (
          <div className="bg-dark-100 rounded-xl border border-dark-300 p-6">
            <div className="flex items-center gap-2 mb-4">
              <TrendingUp className="w-5 h-5 text-green-400" />
              <h2 className="text-lg font-semibold text-gray-200">Skills Improved</h2>
            </div>
            <div className="flex flex-wrap gap-2">
              {digest.skills_improved.map((skill, i) => (
                <span key={i} className="px-3 py-1 bg-green-400/10 text-green-400 rounded-full text-sm">
                  {skill}
                </span>
              ))}
            </div>
          </div>
        )}
      </div>

      {/* Focus Suggestions */}
      {digest.focus_suggestions.length > 0 && (
        <div className="bg-dark-100 rounded-xl border border-dark-300 p-6">
          <h2 className="text-lg font-semibold text-gray-200 mb-4">Focus Suggestions</h2>
          <ul className="space-y-2">
            {digest.focus_suggestions.map((suggestion, i) => (
              <li key={i} className="flex items-start gap-3 text-gray-300">
                <span className="text-primary">•</span>
                {suggestion}
              </li>
            ))}
          </ul>
        </div>
      )}

      {/* Quick Wins */}
      {digest.quick_wins.length > 0 && (
        <div className="bg-primary/10 border border-primary/30 rounded-xl p-6">
          <h2 className="text-lg font-semibold text-gray-200 mb-4">Quick Wins</h2>
          <ul className="space-y-2">
            {digest.quick_wins.map((win, i) => (
              <li key={i} className="flex items-start gap-3 text-gray-300">
                <span className="text-primary">✓</span>
                {win}
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}

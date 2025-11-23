'use client';

import { useState } from 'react';
import api from '@/lib/api';
import toast from 'react-hot-toast';
import { Baby, Lightbulb, BookOpen, ArrowRight, Loader2 } from 'lucide-react';

interface ELI5Result {
  simple_explanation: string;
  analogy?: string;
  why_it_matters?: string;
  simple_example?: string;
  learn_next?: string[];
}

export default function ELI5Page() {
  const [topic, setTopic] = useState('');
  const [result, setResult] = useState<ELI5Result | null>(null);
  const [loading, setLoading] = useState(false);

  const explain = async () => {
    if (!topic.trim()) {
      toast.error('Please enter a topic');
      return;
    }
    setLoading(true);
    try {
      const data = await api.explainELI5(topic);
      setResult(data);
    } catch {
      toast.error('Failed to generate explanation');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="space-y-6 animate-fadeIn">
      <div>
        <h1 className="text-2xl font-bold text-gray-100">ELI5 - Explain Like I'm 5</h1>
        <p className="text-gray-500">Get simple explanations for complex topics</p>
      </div>

      {/* Topic Input */}
      <div className="bg-dark-100 rounded-xl border border-dark-300 p-6">
        <label className="block text-sm text-gray-400 mb-2">What would you like explained?</label>
        <div className="flex gap-3">
          <input
            type="text"
            value={topic}
            onChange={(e) => setTopic(e.target.value)}
            placeholder="E.g., Docker containers, REST APIs, Machine learning"
            className="input flex-1"
            onKeyPress={(e) => e.key === 'Enter' && explain()}
          />
          <button
            onClick={explain}
            disabled={loading}
            className="btn btn-primary flex items-center gap-2"
          >
            {loading ? <Loader2 className="w-4 h-4 animate-spin" /> : <Baby className="w-4 h-4" />}
            Explain
          </button>
        </div>
      </div>

      {/* Explanation Result */}
      {result && (
        <div className="space-y-6">
          {/* Simple Explanation */}
          <div className="bg-primary/10 border border-primary/30 rounded-xl p-6">
            <div className="flex items-center gap-2 mb-4">
              <Baby className="w-5 h-5 text-primary" />
              <h2 className="text-lg font-semibold text-gray-200">Simple Explanation</h2>
            </div>
            <p className="text-gray-300 text-lg leading-relaxed">{result.simple_explanation}</p>
          </div>

          {/* Analogy */}
          {result.analogy && (
            <div className="bg-dark-100 rounded-xl border border-dark-300 p-6">
              <div className="flex items-center gap-2 mb-4">
                <Lightbulb className="w-5 h-5 text-yellow-400" />
                <h2 className="text-lg font-semibold text-gray-200">Think of it like...</h2>
              </div>
              <p className="text-gray-300 italic">{result.analogy}</p>
            </div>
          )}

          {/* Simple Example */}
          {result.simple_example && (
            <div className="bg-dark-100 rounded-xl border border-dark-300 p-6">
              <h2 className="text-lg font-semibold text-gray-200 mb-4">Simple Example</h2>
              <p className="text-gray-300">{result.simple_example}</p>
            </div>
          )}

          {/* Why It Matters */}
          {result.why_it_matters && (
            <div className="bg-dark-100 rounded-xl border border-dark-300 p-6">
              <h2 className="text-lg font-semibold text-gray-200 mb-4">Why Does This Matter?</h2>
              <p className="text-gray-300">{result.why_it_matters}</p>
            </div>
          )}

          {/* Learn Next */}
          {result.learn_next && result.learn_next.length > 0 && (
            <div className="bg-dark-100 rounded-xl border border-dark-300 p-6">
              <div className="flex items-center gap-2 mb-4">
                <BookOpen className="w-5 h-5 text-green-400" />
                <h2 className="text-lg font-semibold text-gray-200">Learn Next</h2>
              </div>
              <div className="flex flex-wrap gap-2">
                {result.learn_next.map((item, i) => (
                  <button
                    key={i}
                    onClick={() => setTopic(item)}
                    className="px-3 py-2 bg-dark-200 hover:bg-dark-300 text-gray-300 rounded-lg text-sm flex items-center gap-2 transition-colors"
                  >
                    {item}
                    <ArrowRight className="w-4 h-4" />
                  </button>
                ))}
              </div>
            </div>
          )}
        </div>
      )}

      {!result && !loading && (
        <div className="text-center py-12 text-gray-500">
          <Baby className="w-12 h-12 mx-auto mb-4 opacity-50" />
          <p>Enter any topic to get a simple explanation</p>
        </div>
      )}
    </div>
  );
}

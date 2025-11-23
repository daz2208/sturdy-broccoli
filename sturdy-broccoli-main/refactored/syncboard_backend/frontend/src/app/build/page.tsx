'use client';
import { useState } from 'react';
import api from '@/lib/api';
import toast from 'react-hot-toast';
import { Lightbulb, Loader2 } from 'lucide-react';

export default function BuildPage() {
  const [suggestions, setSuggestions] = useState<any[]>([]);
  const [loading, setLoading] = useState(false);
  const [maxSuggestions, setMaxSuggestions] = useState(5);

  const getSuggestions = async () => {
    setLoading(true);
    try {
      const data = await api.whatCanIBuild(maxSuggestions, true);
      setSuggestions(data.suggestions);
      if (data.suggestions.length === 0) toast('No suggestions yet. Add more content!', { icon: '💡' });
    } catch (err) { toast.error('Failed to get suggestions'); }
    finally { setLoading(false); }
  };

  return (
    <div className="space-y-6 animate-fadeIn">
      <div className="flex justify-between items-center">
        <div>
          <h1 className="text-2xl font-bold text-gray-100">Build Ideas</h1>
          <p className="text-gray-500">AI-powered project suggestions based on your knowledge</p>
        </div>
        <div className="flex gap-3 items-center">
          <select value={maxSuggestions} onChange={(e) => setMaxSuggestions(Number(e.target.value))} className="input w-auto">
            <option value={3}>3 ideas</option><option value={5}>5 ideas</option><option value={10}>10 ideas</option>
          </select>
          <button onClick={getSuggestions} disabled={loading} className="btn btn-primary flex items-center gap-2">
            {loading ? <Loader2 className="w-4 h-4 animate-spin" /> : <Lightbulb className="w-4 h-4" />}
            {loading ? 'Analyzing...' : 'Get Ideas'}
          </button>
        </div>
      </div>
      {suggestions.length > 0 && (
        <div className="grid gap-4">
          {suggestions.map((s, i) => (
            <div key={i} className="bg-dark-100 rounded-xl border border-dark-300 p-6 border-l-4 border-l-accent-green">
              <h3 className="text-lg font-semibold text-gray-200">{s.title}</h3>
              <p className="text-gray-400 mt-2">{s.description}</p>
              <div className="flex gap-2 mt-3 flex-wrap">
                {s.required_skills?.map((skill: string, j: number) => (
                  <span key={j} className="badge badge-primary">{skill}</span>
                ))}
              </div>
              {s.estimated_effort && <p className="text-sm text-gray-500 mt-3">Effort: {s.estimated_effort}</p>}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

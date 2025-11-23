'use client';

import { useState } from 'react';
import api from '@/lib/api';
import toast from 'react-hot-toast';
import { Search as SearchIcon, FileText, Filter, Save } from 'lucide-react';
import type { SearchResult } from '@/types/api';

export default function SearchPage() {
  const [query, setQuery] = useState('');
  const [results, setResults] = useState<SearchResult[]>([]);
  const [loading, setLoading] = useState(false);
  const [filters, setFilters] = useState({ source_type: '', skill_level: '', cluster_id: '' });

  const handleSearch = async () => {
    if (!query.trim()) {
      toast.error('Please enter a search query');
      return;
    }
    setLoading(true);
    try {
      const response = await api.search({
        q: query,
        top_k: 20,
        source_type: filters.source_type || undefined,
        skill_level: filters.skill_level || undefined,
        cluster_id: filters.cluster_id ? parseInt(filters.cluster_id) : undefined,
      });
      setResults(response.results);
      if (response.results.length === 0) {
        toast('No results found', { icon: '🔍' });
      }
    } catch (err) {
      toast.error('Search failed');
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  const saveSearch = async () => {
    const name = prompt('Enter a name for this search:');
    if (!name) return;
    try {
      await api.saveSearch(name, query, filters);
      toast.success('Search saved!');
    } catch (err) {
      toast.error('Failed to save search');
    }
  };

  return (
    <div className="space-y-6 animate-fadeIn">
      <div>
        <h1 className="text-2xl font-bold text-gray-100">Search</h1>
        <p className="text-gray-500">Semantic search across your knowledge base</p>
      </div>

      {/* Search Bar */}
      <div className="bg-dark-100 rounded-xl border border-dark-300 p-6">
        <div className="flex gap-3">
          <div className="relative flex-1">
            <SearchIcon className="absolute left-4 top-1/2 -translate-y-1/2 w-5 h-5 text-gray-500" />
            <input
              type="text"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              onKeyPress={(e) => e.key === 'Enter' && handleSearch()}
              placeholder="Search your knowledge..."
              className="input pl-12"
            />
          </div>
          <button onClick={handleSearch} disabled={loading} className="btn btn-primary px-8">
            {loading ? 'Searching...' : 'Search'}
          </button>
          {query && (
            <button onClick={saveSearch} className="btn btn-secondary" title="Save this search">
              <Save className="w-5 h-5" />
            </button>
          )}
        </div>

        {/* Filters */}
        <div className="flex gap-4 mt-4 items-center">
          <Filter className="w-4 h-4 text-gray-500" />
          <select
            value={filters.source_type}
            onChange={(e) => setFilters(f => ({ ...f, source_type: e.target.value }))}
            className="input w-auto"
          >
            <option value="">All Sources</option>
            <option value="text">Text</option>
            <option value="url">URL</option>
            <option value="file">File</option>
            <option value="youtube">YouTube</option>
          </select>
          <select
            value={filters.skill_level}
            onChange={(e) => setFilters(f => ({ ...f, skill_level: e.target.value }))}
            className="input w-auto"
          >
            <option value="">All Levels</option>
            <option value="beginner">Beginner</option>
            <option value="intermediate">Intermediate</option>
            <option value="advanced">Advanced</option>
          </select>
        </div>
      </div>

      {/* Results */}
      {results.length > 0 && (
        <div className="space-y-3">
          <h2 className="text-lg font-semibold text-gray-200">{results.length} Results</h2>
          {results.map((result) => (
            <div
              key={result.doc_id}
              className="bg-dark-100 rounded-lg border border-dark-300 p-4 hover:border-primary/50 transition-colors cursor-pointer"
              onClick={() => window.open(`/documents/${result.doc_id}`, '_blank')}
            >
              <div className="flex items-start justify-between">
                <div className="flex items-start gap-3">
                  <FileText className="w-5 h-5 text-primary mt-1" />
                  <div>
                    <h3 className="font-medium text-gray-200">{result.title}</h3>
                    <p className="text-sm text-gray-400 mt-1 line-clamp-2">
                      {result.snippet || result.content?.substring(0, 200)}
                    </p>
                    <div className="flex gap-2 mt-2">
                      <span className="badge badge-primary">{result.source_type}</span>
                      <span className="text-xs text-gray-500">
                        Score: {(result.similarity_score * 100).toFixed(1)}%
                      </span>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

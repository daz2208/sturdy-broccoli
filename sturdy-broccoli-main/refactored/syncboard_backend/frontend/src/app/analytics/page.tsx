'use client';

import { useEffect, useState } from 'react';
import api from '@/lib/api';
import toast from 'react-hot-toast';
import { BarChart3, TrendingUp, FileText, FolderOpen } from 'lucide-react';

export default function AnalyticsPage() {
  const [analytics, setAnalytics] = useState<any>(null);
  const [period, setPeriod] = useState(30);
  const [loading, setLoading] = useState(true);

  useEffect(() => { loadAnalytics(); }, [period]);

  const loadAnalytics = async () => {
    try {
      const data = await api.getAnalytics(period);
      setAnalytics(data);
    } catch (err) {
      toast.error('Failed to load analytics');
    } finally {
      setLoading(false);
    }
  };

  if (loading) return <div className="flex justify-center py-12"><div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary"></div></div>;

  return (
    <div className="space-y-6 animate-fadeIn">
      <div className="flex justify-between items-center">
        <div>
          <h1 className="text-2xl font-bold text-gray-100">Analytics</h1>
          <p className="text-gray-500">Insights into your knowledge base</p>
        </div>
        <select value={period} onChange={(e) => setPeriod(Number(e.target.value))} className="input w-auto">
          <option value={7}>Last 7 days</option>
          <option value={30}>Last 30 days</option>
          <option value={90}>Last 90 days</option>
        </select>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <StatCard title="Total Documents" value={analytics?.overview?.total_docs || 0} icon={FileText} />
        <StatCard title="Clusters" value={analytics?.overview?.clusters || 0} icon={FolderOpen} />
        <StatCard title="Concepts" value={analytics?.overview?.concepts || 0} icon={TrendingUp} />
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <div className="bg-dark-100 rounded-xl border border-dark-300 p-6">
          <h2 className="text-lg font-semibold text-gray-200 mb-4">Top Concepts</h2>
          <div className="space-y-2">
            {analytics?.top_concepts?.slice(0, 10).map((c: any, i: number) => (
              <div key={i} className="flex justify-between items-center py-2 border-b border-dark-300 last:border-0">
                <span className="text-gray-300">{c.concept}</span>
                <span className="badge badge-primary">{c.count}</span>
              </div>
            ))}
          </div>
        </div>

        <div className="bg-dark-100 rounded-xl border border-dark-300 p-6">
          <h2 className="text-lg font-semibold text-gray-200 mb-4">By Source Type</h2>
          <div className="space-y-2">
            {Object.entries(analytics?.distributions?.by_source || {}).map(([source, count]: any) => (
              <div key={source} className="flex justify-between items-center py-2 border-b border-dark-300 last:border-0">
                <span className="text-gray-300">{source}</span>
                <span className="badge badge-success">{count}</span>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}

function StatCard({ title, value, icon: Icon }: { title: string; value: number; icon: any }) {
  return (
    <div className="bg-dark-100 rounded-xl border border-dark-300 p-6">
      <div className="flex items-center justify-between">
        <div>
          <p className="text-sm text-gray-500">{title}</p>
          <p className="text-3xl font-bold text-primary mt-1">{value}</p>
        </div>
        <div className="p-3 bg-dark-200 rounded-lg">
          <Icon className="w-6 h-6 text-primary" />
        </div>
      </div>
    </div>
  );
}

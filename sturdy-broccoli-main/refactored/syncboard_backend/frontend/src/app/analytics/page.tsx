'use client';

import { useEffect, useState, useCallback } from 'react';
import api from '@/lib/api';
import toast from 'react-hot-toast';
import { BarChart3, TrendingUp, FileText, FolderOpen, Brain, Layers, Wifi, RefreshCw } from 'lucide-react';
import { useWebSocket } from '@/hooks/useWebSocket';

export default function AnalyticsPage() {
  const [analytics, setAnalytics] = useState<any>(null);
  const [period, setPeriod] = useState(30);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);

  // WebSocket for real-time updates
  const { isConnected, on } = useWebSocket();

  const loadAnalytics = useCallback(async () => {
    try {
      const data = await api.getAnalytics(period);
      setAnalytics(data);
    } catch (err) {
      toast.error('Failed to load analytics');
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, [period]);

  useEffect(() => {
    loadAnalytics();

    // Listen for document events to refresh analytics
    const unsubCreated = on('document_created', () => {
      loadAnalytics();
    });

    const unsubDeleted = on('document_deleted', () => {
      loadAnalytics();
    });

    return () => {
      unsubCreated();
      unsubDeleted();
    };
  }, [period, on, loadAnalytics]);

  const handleRefresh = () => {
    setRefreshing(true);
    loadAnalytics();
  };

  if (loading) return (
    <div className="flex justify-center py-12">
      <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary"></div>
    </div>
  );

  return (
    <div className="space-y-6 animate-fadeIn">
      <div className="flex justify-between items-center">
        <div>
          <div className="flex items-center gap-3">
            <h1 className="text-2xl font-bold text-gray-100">Analytics</h1>
            {isConnected && (
              <span className="flex items-center gap-1 text-xs text-green-500 bg-green-500/10 px-2 py-1 rounded">
                <Wifi className="w-3 h-3" />
                Live
              </span>
            )}
          </div>
          <p className="text-gray-500">Insights into your knowledge base</p>
        </div>
        <div className="flex gap-2 items-center">
          <button
            onClick={handleRefresh}
            disabled={refreshing}
            className="btn btn-secondary p-2"
            title="Refresh analytics"
          >
            <RefreshCw className={`w-4 h-4 ${refreshing ? 'animate-spin' : ''}`} />
          </button>
          <select value={period} onChange={(e) => setPeriod(Number(e.target.value))} className="input w-auto">
            <option value={7}>Last 7 days</option>
            <option value={30}>Last 30 days</option>
            <option value={90}>Last 90 days</option>
          </select>
        </div>
      </div>

      {/* Overview Stats */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <StatCard title="Total Documents" value={analytics?.overview?.total_docs || 0} icon={FileText} color="primary" />
        <StatCard title="Clusters" value={analytics?.overview?.clusters || 0} icon={FolderOpen} color="purple" />
        <StatCard title="Concepts" value={analytics?.overview?.concepts || 0} icon={Brain} color="green" />
        <StatCard title="Total Chunks" value={analytics?.overview?.total_chunks || 0} icon={Layers} color="blue" />
      </div>

      {/* Distributions */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Top Concepts */}
        <div className="bg-dark-100 rounded-xl border border-dark-300 p-6">
          <h2 className="text-lg font-semibold text-gray-200 mb-4 flex items-center gap-2">
            <TrendingUp className="w-5 h-5 text-primary" />
            Top Concepts
          </h2>
          {analytics?.top_concepts?.length > 0 ? (
            <div className="space-y-2">
              {analytics.top_concepts.slice(0, 10).map((c: any, i: number) => (
                <div key={i} className="flex justify-between items-center py-2 border-b border-dark-300 last:border-0">
                  <span className="text-gray-300 truncate mr-2">{c.concept}</span>
                  <span className="badge badge-primary whitespace-nowrap">{c.count}</span>
                </div>
              ))}
            </div>
          ) : (
            <p className="text-gray-500 text-sm">No concepts extracted yet</p>
          )}
        </div>

        {/* By Source Type */}
        <div className="bg-dark-100 rounded-xl border border-dark-300 p-6">
          <h2 className="text-lg font-semibold text-gray-200 mb-4 flex items-center gap-2">
            <FileText className="w-5 h-5 text-accent-green" />
            By Source Type
          </h2>
          {Object.keys(analytics?.distributions?.by_source || {}).length > 0 ? (
            <div className="space-y-2">
              {Object.entries(analytics?.distributions?.by_source || {}).map(([source, count]: any) => (
                <div key={source} className="flex justify-between items-center py-2 border-b border-dark-300 last:border-0">
                  <span className="text-gray-300 capitalize">{source}</span>
                  <span className="badge badge-success">{count}</span>
                </div>
              ))}
            </div>
          ) : (
            <p className="text-gray-500 text-sm">No documents uploaded yet</p>
          )}
        </div>

        {/* By Skill Level */}
        <div className="bg-dark-100 rounded-xl border border-dark-300 p-6">
          <h2 className="text-lg font-semibold text-gray-200 mb-4 flex items-center gap-2">
            <BarChart3 className="w-5 h-5 text-accent-purple" />
            By Skill Level
          </h2>
          {Object.keys(analytics?.distributions?.by_skill_level || {}).length > 0 ? (
            <div className="space-y-2">
              {Object.entries(analytics?.distributions?.by_skill_level || {}).map(([level, count]: any) => (
                <div key={level} className="flex justify-between items-center py-2 border-b border-dark-300 last:border-0">
                  <span className="text-gray-300 capitalize">{level || 'Unspecified'}</span>
                  <span className="badge badge-purple">{count}</span>
                </div>
              ))}
            </div>
          ) : (
            <p className="text-gray-500 text-sm">No skill levels assigned yet</p>
          )}
        </div>
      </div>

      {/* Time Series / Recent Activity */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Documents Over Time */}
        <div className="bg-dark-100 rounded-xl border border-dark-300 p-6">
          <h2 className="text-lg font-semibold text-gray-200 mb-4">Documents Over Time</h2>
          {analytics?.time_series?.length > 0 ? (
            <div className="space-y-1">
              {analytics.time_series.slice(-7).map((day: any, i: number) => {
                const maxCount = Math.max(...analytics.time_series.map((d: any) => d.count || 0), 1);
                const percentage = ((day.count || 0) / maxCount) * 100;
                return (
                  <div key={i} className="flex items-center gap-2">
                    <span className="text-xs text-gray-500 w-20">{day.date}</span>
                    <div className="flex-1 bg-dark-300 rounded-full h-2">
                      <div
                        className="bg-primary h-2 rounded-full transition-all"
                        style={{ width: `${percentage}%` }}
                      />
                    </div>
                    <span className="text-xs text-gray-400 w-8 text-right">{day.count || 0}</span>
                  </div>
                );
              })}
            </div>
          ) : (
            <p className="text-gray-500 text-sm">No activity in this period</p>
          )}
        </div>

        {/* Recent Activity */}
        <div className="bg-dark-100 rounded-xl border border-dark-300 p-6">
          <h2 className="text-lg font-semibold text-gray-200 mb-4">Recent Activity</h2>
          {analytics?.recent_activity?.length > 0 ? (
            <div className="space-y-3">
              {analytics.recent_activity.slice(0, 5).map((item: any, i: number) => (
                <div key={i} className="flex justify-between items-center py-2 border-b border-dark-300 last:border-0">
                  <div>
                    <p className="text-sm text-gray-300">{item.action}</p>
                    <p className="text-xs text-gray-500">{item.details}</p>
                  </div>
                  <span className="text-xs text-gray-500 whitespace-nowrap">{item.timestamp}</span>
                </div>
              ))}
            </div>
          ) : (
            <p className="text-gray-500 text-sm">No recent activity</p>
          )}
        </div>
      </div>
    </div>
  );
}

function StatCard({ title, value, icon: Icon, color }: { title: string; value: number; icon: any; color: string }) {
  const colors: Record<string, string> = {
    primary: 'text-primary',
    purple: 'text-accent-purple',
    green: 'text-accent-green',
    blue: 'text-accent-blue',
    orange: 'text-accent-orange',
  };

  return (
    <div className="bg-dark-100 rounded-xl border border-dark-300 p-6">
      <div className="flex items-center justify-between">
        <div>
          <p className="text-sm text-gray-500">{title}</p>
          <p className={`text-3xl font-bold mt-1 ${colors[color] || 'text-primary'}`}>{value}</p>
        </div>
        <div className="p-3 bg-dark-200 rounded-lg">
          <Icon className={`w-6 h-6 ${colors[color] || 'text-primary'}`} />
        </div>
      </div>
    </div>
  );
}

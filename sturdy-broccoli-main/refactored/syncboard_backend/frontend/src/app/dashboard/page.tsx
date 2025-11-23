'use client';

import { useEffect, useState } from 'react';
import api from '@/lib/api';
import toast from 'react-hot-toast';
import { FileText, FolderOpen, Brain, Cpu, Upload, Search, Lightbulb, Activity } from 'lucide-react';
import Link from 'next/link';

interface DashboardStats {
  documents: number;
  clusters: number;
  concepts: number;
  health: {
    status: string;
    database: boolean;
    openai: boolean;
  };
}

interface RecentActivity {
  action: string;
  timestamp: string;
  details: string;
}

export default function DashboardPage() {
  const [stats, setStats] = useState<DashboardStats | null>(null);
  const [activity, setActivity] = useState<RecentActivity[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    loadDashboard();
  }, []);

  const loadDashboard = async () => {
    try {
      const [healthData, analyticsData] = await Promise.all([
        api.getHealth(),
        api.getAnalytics(7),
      ]);

      setStats({
        documents: healthData.statistics.documents,
        clusters: healthData.statistics.clusters,
        concepts: analyticsData.top_concepts?.length || 0,
        health: {
          status: healthData.status,
          database: healthData.dependencies.database,
          openai: healthData.dependencies.openai_configured,
        },
      });

      setActivity(analyticsData.recent_activity?.slice(0, 5) || []);
    } catch (err) {
      toast.error('Failed to load dashboard');
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary"></div>
      </div>
    );
  }

  return (
    <div className="space-y-6 animate-fadeIn">
      {/* Header */}
      <div className="flex justify-between items-center">
        <div>
          <h1 className="text-2xl font-bold text-gray-100">Dashboard</h1>
          <p className="text-gray-500">Welcome back! Here&apos;s your knowledge overview.</p>
        </div>
        <div className="flex gap-3">
          <Link href="/documents" className="btn btn-secondary flex items-center gap-2">
            <Upload className="w-4 h-4" /> Upload Content
          </Link>
          <Link href="/search" className="btn btn-primary flex items-center gap-2">
            <Search className="w-4 h-4" /> Search
          </Link>
        </div>
      </div>

      {/* Stats Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        <StatCard
          title="Documents"
          value={stats?.documents || 0}
          icon={FileText}
          color="primary"
          href="/documents"
        />
        <StatCard
          title="Clusters"
          value={stats?.clusters || 0}
          icon={FolderOpen}
          color="purple"
          href="/clusters"
        />
        <StatCard
          title="Concepts"
          value={stats?.concepts || 0}
          icon={Brain}
          color="green"
          href="/analytics"
        />
        <StatCard
          title="System Status"
          value={stats?.health.status === 'healthy' ? 'Online' : 'Issues'}
          icon={Cpu}
          color={stats?.health.status === 'healthy' ? 'green' : 'orange'}
          href="/admin"
        />
      </div>

      {/* Quick Actions */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Quick Actions */}
        <div className="bg-dark-100 rounded-xl border border-dark-300 p-6">
          <h2 className="text-lg font-semibold text-gray-200 mb-4">Quick Actions</h2>
          <div className="grid grid-cols-2 gap-3">
            <QuickAction href="/build" icon={Lightbulb} label="Get Build Ideas" />
            <QuickAction href="/knowledge-tools/gaps" icon={Brain} label="Analyze Gaps" />
            <QuickAction href="/knowledge-tools/chat" icon={Search} label="Chat with KB" />
            <QuickAction href="/knowledge-tools/flashcards" icon={FileText} label="Create Flashcards" />
          </div>
        </div>

        {/* Recent Activity */}
        <div className="bg-dark-100 rounded-xl border border-dark-300 p-6">
          <h2 className="text-lg font-semibold text-gray-200 mb-4 flex items-center gap-2">
            <Activity className="w-5 h-5 text-primary" />
            Recent Activity
          </h2>
          {activity.length > 0 ? (
            <div className="space-y-3">
              {activity.map((item, i) => (
                <div key={i} className="flex justify-between items-center py-2 border-b border-dark-300 last:border-0">
                  <div>
                    <p className="text-sm text-gray-300">{item.action}</p>
                    <p className="text-xs text-gray-500">{item.details}</p>
                  </div>
                  <span className="text-xs text-gray-500">{item.timestamp}</span>
                </div>
              ))}
            </div>
          ) : (
            <p className="text-gray-500 text-sm">No recent activity</p>
          )}
        </div>
      </div>

      {/* Features Overview */}
      <div className="bg-dark-100 rounded-xl border border-dark-300 p-6">
        <h2 className="text-lg font-semibold text-gray-200 mb-4">Available Features</h2>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          {features.map((feature) => (
            <Link
              key={feature.href}
              href={feature.href}
              className="p-4 bg-dark-200 rounded-lg hover:bg-dark-300 transition-colors"
            >
              <feature.icon className={`w-6 h-6 mb-2 ${feature.color}`} />
              <h3 className="font-medium text-gray-200">{feature.name}</h3>
              <p className="text-xs text-gray-500 mt-1">{feature.description}</p>
            </Link>
          ))}
        </div>
      </div>
    </div>
  );
}

function StatCard({
  title,
  value,
  icon: Icon,
  color,
  href,
}: {
  title: string;
  value: number | string;
  icon: React.ComponentType<{ className?: string }>;
  color: string;
  href: string;
}) {
  const colors: Record<string, string> = {
    primary: 'text-primary border-primary',
    purple: 'text-accent-purple border-accent-purple',
    green: 'text-accent-green border-accent-green',
    orange: 'text-accent-orange border-accent-orange',
  };

  return (
    <Link
      href={href}
      className="bg-dark-100 rounded-xl border border-dark-300 p-6 hover:border-dark-200 transition-colors"
    >
      <div className="flex items-center justify-between">
        <div>
          <p className="text-sm text-gray-500">{title}</p>
          <p className={`text-3xl font-bold mt-1 ${colors[color]}`}>{value}</p>
        </div>
        <div className={`p-3 rounded-lg bg-dark-200 ${colors[color]}`}>
          <Icon className="w-6 h-6" />
        </div>
      </div>
    </Link>
  );
}

function QuickAction({
  href,
  icon: Icon,
  label,
}: {
  href: string;
  icon: React.ComponentType<{ className?: string }>;
  label: string;
}) {
  return (
    <Link
      href={href}
      className="flex items-center gap-3 p-3 bg-dark-200 rounded-lg hover:bg-dark-300 transition-colors"
    >
      <Icon className="w-5 h-5 text-primary" />
      <span className="text-sm text-gray-300">{label}</span>
    </Link>
  );
}

const features = [
  { name: 'Documents', href: '/documents', icon: FileText, color: 'text-primary', description: 'Manage your uploads' },
  { name: 'Search', href: '/search', icon: Search, color: 'text-accent-blue', description: 'Semantic search' },
  { name: 'Analytics', href: '/analytics', icon: Activity, color: 'text-accent-green', description: 'Usage insights' },
  { name: 'Build Ideas', href: '/build', icon: Lightbulb, color: 'text-accent-orange', description: 'AI suggestions' },
  { name: 'KB Chat', href: '/knowledge-tools/chat', icon: Brain, color: 'text-accent-purple', description: 'Talk to your KB' },
  { name: 'Flashcards', href: '/knowledge-tools/flashcards', icon: FileText, color: 'text-accent-orange', description: 'Study cards' },
  { name: 'Integrations', href: '/integrations', icon: Cpu, color: 'text-accent-blue', description: 'Cloud connections' },
  { name: 'Projects', href: '/projects', icon: FolderOpen, color: 'text-accent-green', description: 'Track progress' },
];

'use client';

import { useState, useEffect } from 'react';
import api from '@/lib/api';

interface Usage {
  period_start: string;
  period_end: string;
  api_calls: number;
  documents_uploaded: number;
  ai_requests: number;
  storage_bytes: number;
  search_queries: number;
  build_suggestions: number;
  limits: {
    api_calls_per_day: number;
    documents_per_month: number;
    ai_requests_per_day: number;
    storage_mb: number;
    [key: string]: number;
  };
  usage_percentage: {
    api_calls: number;
    documents: number;
    ai_requests: number;
    storage: number;
    [key: string]: number;
  };
}

interface Subscription {
  plan: string;
  status: string;
  started_at: string;
  expires_at: string | null;
  trial_ends_at: string | null;
  limits: Record<string, unknown>;
}

interface Plan {
  id: string;
  name: string;
  price_monthly: number;
  limits: Record<string, number>;
  features: string[];
}

function UsageBar({ label, used, limit, percentage }: {
  label: string;
  used: number;
  limit: number;
  percentage: number;
}) {
  const isUnlimited = limit === -1;
  const barColor = percentage > 90 ? 'bg-red-500' : percentage > 70 ? 'bg-yellow-500' : 'bg-green-500';

  return (
    <div className="mb-4">
      <div className="flex justify-between text-sm mb-1">
        <span className="font-medium">{label}</span>
        <span className="text-gray-600">
          {used.toLocaleString()} / {isUnlimited ? 'Unlimited' : limit.toLocaleString()}
        </span>
      </div>
      <div className="w-full bg-gray-200 rounded-full h-2.5">
        <div
          className={`${barColor} h-2.5 rounded-full transition-all duration-300`}
          style={{ width: `${isUnlimited ? 0 : Math.min(percentage, 100)}%` }}
        />
      </div>
      {percentage > 90 && !isUnlimited && (
        <p className="text-red-500 text-xs mt-1">Approaching limit!</p>
      )}
    </div>
  );
}

function PlanCard({ plan, currentPlan, onUpgrade }: {
  plan: Plan;
  currentPlan: string;
  onUpgrade: (planId: string) => void;
}) {
  const isCurrentPlan = plan.id === currentPlan;
  const isPlanHigher = ['starter', 'pro', 'enterprise'].indexOf(plan.id) >
                       ['starter', 'pro', 'enterprise'].indexOf(currentPlan);

  return (
    <div className={`border rounded-lg p-6 ${isCurrentPlan ? 'border-blue-500 bg-blue-50' : 'border-gray-200'}`}>
      <h3 className="text-lg font-bold">{plan.name}</h3>
      <p className="text-2xl font-bold mt-2">
        ${plan.price_monthly}
        <span className="text-sm font-normal text-gray-500">/month</span>
      </p>

      <ul className="mt-4 space-y-2">
        {plan.features.map((feature, idx) => (
          <li key={idx} className="flex items-start text-sm">
            <svg className="w-4 h-4 text-green-500 mr-2 mt-0.5" fill="currentColor" viewBox="0 0 20 20">
              <path fillRule="evenodd" d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z" clipRule="evenodd" />
            </svg>
            {feature}
          </li>
        ))}
      </ul>

      <div className="mt-4 text-xs text-gray-500 space-y-1">
        <p>API calls: {plan.limits.api_calls_per_day === -1 ? 'Unlimited' : plan.limits.api_calls_per_day.toLocaleString()}/day</p>
        <p>Documents: {plan.limits.documents_per_month === -1 ? 'Unlimited' : plan.limits.documents_per_month.toLocaleString()}/month</p>
        <p>Storage: {plan.limits.storage_mb === -1 ? 'Unlimited' : `${(plan.limits.storage_mb / 1024).toFixed(1)} GB`}</p>
      </div>

      <button
        onClick={() => onUpgrade(plan.id)}
        disabled={isCurrentPlan || !isPlanHigher}
        className={`mt-4 w-full py-2 px-4 rounded-md font-medium transition-colors ${
          isCurrentPlan
            ? 'bg-gray-100 text-gray-500 cursor-not-allowed'
            : isPlanHigher
              ? 'bg-blue-600 text-white hover:bg-blue-700'
              : 'bg-gray-100 text-gray-400 cursor-not-allowed'
        }`}
      >
        {isCurrentPlan ? 'Current Plan' : isPlanHigher ? 'Upgrade' : 'Downgrade N/A'}
      </button>
    </div>
  );
}

export default function UsageDashboard() {
  const [usage, setUsage] = useState<Usage | null>(null);
  const [subscription, setSubscription] = useState<Subscription | null>(null);
  const [plans, setPlans] = useState<Plan[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [upgrading, setUpgrading] = useState(false);

  useEffect(() => {
    loadData();
  }, []);

  const loadData = async () => {
    try {
      setLoading(true);
      const [usageRes, subRes, plansRes] = await Promise.all([
        api.getUsage(),
        api.getSubscription(),
        api.getPlans()
      ]);
      setUsage(usageRes as Usage);
      setSubscription(subRes as Subscription);
      setPlans(plansRes as Plan[]);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load usage data');
    } finally {
      setLoading(false);
    }
  };

  const handleUpgrade = async (planId: string) => {
    if (!confirm(`Upgrade to ${planId} plan?`)) return;

    try {
      setUpgrading(true);
      await api.upgradeSubscription(planId);
      await loadData();
      alert('Plan upgraded successfully!');
    } catch (err) {
      alert(err instanceof Error ? err.message : 'Upgrade failed');
    } finally {
      setUpgrading(false);
    }
  };

  const formatBytes = (bytes: number) => {
    if (bytes === 0) return '0 B';
    const k = 1024;
    const sizes = ['B', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600"></div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="bg-red-50 border border-red-200 rounded-lg p-4">
        <p className="text-red-600">{error}</p>
        <button onClick={loadData} className="mt-2 text-sm text-red-700 underline">
          Retry
        </button>
      </div>
    );
  }

  return (
    <div className="space-y-8">
      {/* Current Plan Summary */}
      <div className="bg-white rounded-lg border p-6">
        <div className="flex justify-between items-start">
          <div>
            <h2 className="text-xl font-bold">Current Plan: {subscription?.plan.toUpperCase()}</h2>
            <p className="text-gray-500 text-sm mt-1">
              Status: <span className={subscription?.status === 'active' ? 'text-green-600' : 'text-yellow-600'}>
                {subscription?.status}
              </span>
            </p>
            {subscription?.trial_ends_at && (
              <p className="text-yellow-600 text-sm mt-1">
                Trial ends: {new Date(subscription.trial_ends_at).toLocaleDateString()}
              </p>
            )}
          </div>
          <div className="text-right text-sm text-gray-500">
            <p>Billing period:</p>
            <p>{usage && new Date(usage.period_start).toLocaleDateString()} - {usage && new Date(usage.period_end).toLocaleDateString()}</p>
          </div>
        </div>
      </div>

      {/* Usage Stats */}
      <div className="bg-white rounded-lg border p-6">
        <h3 className="text-lg font-semibold mb-4">Usage This Period</h3>

        {usage && (
          <div className="grid md:grid-cols-2 gap-6">
            <div>
              <UsageBar
                label="API Calls (today)"
                used={usage.api_calls}
                limit={usage.limits.api_calls_per_day}
                percentage={usage.usage_percentage.api_calls}
              />
              <UsageBar
                label="Documents Uploaded"
                used={usage.documents_uploaded}
                limit={usage.limits.documents_per_month}
                percentage={usage.usage_percentage.documents}
              />
              <UsageBar
                label="AI Requests (today)"
                used={usage.ai_requests}
                limit={usage.limits.ai_requests_per_day}
                percentage={usage.usage_percentage.ai_requests}
              />
            </div>
            <div>
              <UsageBar
                label="Storage Used"
                used={usage.storage_bytes}
                limit={usage.limits.storage_mb * 1024 * 1024}
                percentage={usage.usage_percentage.storage}
              />

              <div className="mt-4 grid grid-cols-2 gap-4">
                <div className="bg-gray-50 rounded-lg p-4">
                  <p className="text-gray-500 text-sm">Search Queries</p>
                  <p className="text-2xl font-bold">{usage.search_queries.toLocaleString()}</p>
                </div>
                <div className="bg-gray-50 rounded-lg p-4">
                  <p className="text-gray-500 text-sm">Build Suggestions</p>
                  <p className="text-2xl font-bold">{usage.build_suggestions.toLocaleString()}</p>
                </div>
              </div>

              <div className="mt-4 bg-blue-50 rounded-lg p-4">
                <p className="text-gray-500 text-sm">Total Storage</p>
                <p className="text-xl font-bold">{formatBytes(usage.storage_bytes)}</p>
                <p className="text-xs text-gray-400">
                  of {usage.limits.storage_mb === -1 ? 'Unlimited' : `${(usage.limits.storage_mb / 1024).toFixed(1)} GB`}
                </p>
              </div>
            </div>
          </div>
        )}
      </div>

      {/* Available Plans */}
      <div>
        <h3 className="text-lg font-semibold mb-4">Available Plans</h3>
        <div className="grid md:grid-cols-4 gap-4">
          {plans.map(plan => (
            <PlanCard
              key={plan.id}
              plan={plan}
              currentPlan={subscription?.plan || 'free'}
              onUpgrade={handleUpgrade}
            />
          ))}
        </div>
      </div>

      {upgrading && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
          <div className="bg-white rounded-lg p-6">
            <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600 mx-auto"></div>
            <p className="mt-2 text-center">Processing upgrade...</p>
          </div>
        </div>
      )}
    </div>
  );
}

'use client';

import { useState, useEffect } from 'react';
import api from '@/lib/api';
import toast from 'react-hot-toast';
import {
  Bot,
  Brain,
  Zap,
  Target,
  Lightbulb,
  TrendingUp,
  Clock,
  CheckCircle,
  XCircle,
  Play,
  AlertTriangle,
  RefreshCw,
  Activity,
  Eye,
  Loader2,
  ChevronDown,
  ChevronRight,
  Sparkles,
  FlaskConical,
  GraduationCap,
  Shield,
  Rocket
} from 'lucide-react';

interface AgentOverview {
  learning_agent: {
    role: string;
    description: string;
    status: string;
    mode: string;
    current_strategy: string;
    total_observations: number;
    total_actions: number;
    autonomous_rules_created: number;
    accuracy_trend?: string;
  };
  maverick_agent: {
    role: string;
    description: string;
    mood: string;
    curiosity: number;
    confidence: number;
    hypotheses_proposed: number;
    hypotheses_validated: number;
    hypotheses_applied: number;
  };
  collaboration: {
    description: string;
    maverick_hypotheses: { proposed: number; validated: number; applied: number };
    active_tests: number;
    recent_insights: string[];
    expertise: Record<string, number>;
    note?: string;
  };
}

interface Hypothesis {
  id: string;
  category: string;
  description: string;
  target?: string;
  reasoning?: string;
  expected_improvement?: string;
  created_at?: string;
  test_start?: string;
  baseline_metrics?: any;
  status?: string;
  improvement_score?: number;
}

interface Rule {
  id: number;
  type: string;
  condition: any;
  action: any;
  confidence: number;
  times_applied: number;
  times_overridden: number;
  active: boolean;
  created_at: string;
  accuracy?: number | null;
}

function StatCard({ label, value, icon: Icon, color = 'blue' }: {
  label: string;
  value: string | number;
  icon: any;
  color?: string;
}) {
  const colorClasses = {
    blue: 'text-blue-400 bg-blue-500/20',
    green: 'text-green-400 bg-green-500/20',
    yellow: 'text-yellow-400 bg-yellow-500/20',
    purple: 'text-purple-400 bg-purple-500/20',
    red: 'text-red-400 bg-red-500/20',
  }[color] || 'text-blue-400 bg-blue-500/20';

  return (
    <div className="bg-dark-100 rounded-xl border border-dark-300 p-4">
      <div className="flex items-center gap-3">
        <div className={`p-2 rounded-lg ${colorClasses}`}>
          <Icon className="w-5 h-5" />
        </div>
        <div>
          <p className="text-2xl font-bold text-white">{value}</p>
          <p className="text-sm text-gray-500">{label}</p>
        </div>
      </div>
    </div>
  );
}

function MoodIndicator({ mood }: { mood: string }) {
  const config = {
    curious: { color: 'text-blue-400', bg: 'bg-blue-500/20' },
    confident: { color: 'text-green-400', bg: 'bg-green-500/20' },
    cautious: { color: 'text-yellow-400', bg: 'bg-yellow-500/20' },
    determined: { color: 'text-purple-400', bg: 'bg-purple-500/20' },
    excited: { color: 'text-pink-400', bg: 'bg-pink-500/20' },
  }[mood] || { color: 'text-gray-400', bg: 'bg-gray-500/20' };

  return (
    <span className={`px-3 py-1 rounded-full text-sm font-medium ${config.color} ${config.bg}`}>
      {mood}
    </span>
  );
}

function StrategyBadge({ strategy }: { strategy: string }) {
  const config = {
    conservative: { color: 'text-blue-400', bg: 'bg-blue-500/20', icon: Shield },
    balanced: { color: 'text-green-400', bg: 'bg-green-500/20', icon: Target },
    aggressive: { color: 'text-orange-400', bg: 'bg-orange-500/20', icon: Rocket },
  }[strategy] || { color: 'text-gray-400', bg: 'bg-gray-500/20', icon: Target };

  const Icon = config.icon;

  return (
    <span className={`px-3 py-1 rounded-full text-sm font-medium flex items-center gap-1 ${config.color} ${config.bg}`}>
      <Icon className="w-3 h-3" />
      {strategy}
    </span>
  );
}

function HypothesisCard({ hypothesis, type }: { hypothesis: Hypothesis; type: 'pending' | 'testing' | 'result' }) {
  const statusColors = {
    pending: 'border-yellow-500/30 bg-yellow-500/5',
    testing: 'border-blue-500/30 bg-blue-500/5',
    validated: 'border-green-500/30 bg-green-500/5',
    rejected: 'border-red-500/30 bg-red-500/5',
    applied: 'border-purple-500/30 bg-purple-500/5',
  };

  const borderColor = type === 'pending' ? statusColors.pending
    : type === 'testing' ? statusColors.testing
    : statusColors[hypothesis.status as keyof typeof statusColors] || statusColors.pending;

  return (
    <div className={`rounded-lg border p-4 ${borderColor}`}>
      <div className="flex justify-between items-start mb-2">
        <span className="text-xs uppercase tracking-wide text-gray-500">{hypothesis.category}</span>
        {type === 'result' && hypothesis.status && (
          <span className={`text-xs px-2 py-0.5 rounded ${
            hypothesis.status === 'validated' ? 'bg-green-500/20 text-green-400' :
            hypothesis.status === 'rejected' ? 'bg-red-500/20 text-red-400' :
            'bg-purple-500/20 text-purple-400'
          }`}>
            {hypothesis.status}
          </span>
        )}
      </div>
      <p className="text-gray-200 font-medium">{hypothesis.description}</p>
      {hypothesis.target && (
        <p className="text-sm text-gray-500 mt-1">Target: {hypothesis.target}</p>
      )}
      {hypothesis.reasoning && (
        <p className="text-sm text-gray-400 mt-2 italic">"{hypothesis.reasoning}"</p>
      )}
      {hypothesis.improvement_score !== undefined && (
        <div className="mt-2 flex items-center gap-2">
          <span className="text-xs text-gray-500">Improvement:</span>
          <span className={`text-sm font-medium ${
            hypothesis.improvement_score > 0 ? 'text-green-400' : 'text-red-400'
          }`}>
            {hypothesis.improvement_score > 0 ? '+' : ''}{(hypothesis.improvement_score * 100).toFixed(1)}%
          </span>
        </div>
      )}
    </div>
  );
}

function RuleCard({ rule }: { rule: Rule }) {
  const accuracy = rule.times_applied + rule.times_overridden > 0
    ? (rule.times_applied / (rule.times_applied + rule.times_overridden)) * 100
    : null;

  return (
    <div className={`rounded-lg border p-4 ${rule.active ? 'border-dark-300 bg-dark-100' : 'border-dark-400 bg-dark-200 opacity-60'}`}>
      <div className="flex justify-between items-start mb-2">
        <span className="text-xs uppercase tracking-wide text-purple-400">{rule.type}</span>
        <div className="flex items-center gap-2">
          {accuracy !== null && (
            <span className={`text-xs px-2 py-0.5 rounded ${
              accuracy >= 80 ? 'bg-green-500/20 text-green-400' :
              accuracy >= 50 ? 'bg-yellow-500/20 text-yellow-400' :
              'bg-red-500/20 text-red-400'
            }`}>
              {accuracy.toFixed(0)}% accurate
            </span>
          )}
          <span className={`w-2 h-2 rounded-full ${rule.active ? 'bg-green-400' : 'bg-gray-500'}`} />
        </div>
      </div>
      <div className="space-y-1">
        <p className="text-sm text-gray-300">
          <span className="text-gray-500">If:</span> {JSON.stringify(rule.condition)}
        </p>
        <p className="text-sm text-gray-300">
          <span className="text-gray-500">Then:</span> {JSON.stringify(rule.action)}
        </p>
      </div>
      <div className="mt-3 flex items-center gap-4 text-xs text-gray-500">
        <span>Applied: {rule.times_applied}x</span>
        <span>Overridden: {rule.times_overridden}x</span>
        <span>Confidence: {(rule.confidence * 100).toFixed(0)}%</span>
      </div>
    </div>
  );
}

export default function AgentMonitorPage() {
  const [overview, setOverview] = useState<AgentOverview | null>(null);
  const [hypotheses, setHypotheses] = useState<{
    pending: Hypothesis[];
    active_tests: Hypothesis[];
    recent_results: Hypothesis[];
  } | null>(null);
  const [rules, setRules] = useState<Rule[]>([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [activeTab, setActiveTab] = useState<'overview' | 'maverick' | 'learning' | 'rules'>('overview');
  const [triggeringTask, setTriggeringTask] = useState<string | null>(null);

  const loadData = async (showRefreshing = false) => {
    if (showRefreshing) setRefreshing(true);
    else setLoading(true);

    try {
      const [overviewData, hypothesesData, rulesData] = await Promise.all([
        api.getAgentsOverview(),
        api.getMaverickHypotheses(),
        api.getLearnedRules()
      ]);

      setOverview(overviewData);
      setHypotheses({
        pending: hypothesesData.pending || [],
        active_tests: hypothesesData.active_tests || [],
        recent_results: hypothesesData.recent_results || []
      });
      setRules(rulesData.rules || []);
    } catch (err) {
      console.error('Failed to load agent data:', err);
      toast.error('Failed to load agent data');
    }

    setLoading(false);
    setRefreshing(false);
  };

  useEffect(() => {
    loadData();
    // Auto-refresh every 30 seconds
    const interval = setInterval(() => loadData(true), 30000);
    return () => clearInterval(interval);
  }, []);

  const triggerTask = async (agent: 'learning' | 'maverick', taskName: string) => {
    setTriggeringTask(taskName);
    try {
      if (agent === 'learning') {
        await api.triggerLearningAgentTask(taskName);
      } else {
        await api.triggerMaverickTask(taskName);
      }
      toast.success(`Task "${taskName}" triggered`);
      setTimeout(() => loadData(true), 2000);
    } catch (err) {
      toast.error(`Failed to trigger ${taskName}`);
    }
    setTriggeringTask(null);
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-[60vh]">
        <Loader2 className="w-8 h-8 animate-spin text-accent-blue" />
      </div>
    );
  }

  return (
    <div className="space-y-6 animate-fadeIn">
      {/* Header */}
      <div className="flex justify-between items-start">
        <div>
          <h1 className="text-2xl font-bold text-gray-100 flex items-center gap-3">
            <Bot className="w-7 h-7 text-accent-purple" />
            Agent Monitor
          </h1>
          <p className="text-gray-500 mt-1">
            Watch your autonomous agents learn, challenge, and improve
          </p>
        </div>
        <button
          onClick={() => loadData(true)}
          className="btn btn-ghost"
          disabled={refreshing}
        >
          <RefreshCw className={`w-4 h-4 ${refreshing ? 'animate-spin' : ''}`} />
        </button>
      </div>

      {/* Tabs */}
      <div className="flex gap-2 border-b border-dark-300 pb-2">
        {[
          { id: 'overview', label: 'Overview', icon: Activity },
          { id: 'maverick', label: 'Maverick', icon: Zap },
          { id: 'learning', label: 'Learning Agent', icon: Brain },
          { id: 'rules', label: 'Learned Rules', icon: GraduationCap }
        ].map(tab => {
          const Icon = tab.icon;
          return (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id as any)}
              className={`px-4 py-2 rounded-lg flex items-center gap-2 transition-colors ${
                activeTab === tab.id
                  ? 'bg-accent-purple/20 text-accent-purple'
                  : 'text-gray-400 hover:text-white hover:bg-dark-200'
              }`}
            >
              <Icon className="w-4 h-4" />
              {tab.label}
            </button>
          );
        })}
      </div>

      {/* Overview Tab */}
      {activeTab === 'overview' && overview && (
        <div className="space-y-6">
          {/* Agent Cards */}
          <div className="grid md:grid-cols-2 gap-6">
            {/* Learning Agent */}
            <div className="bg-dark-100 rounded-xl border border-dark-300 p-6">
              <div className="flex items-center gap-3 mb-4">
                <div className="p-3 bg-blue-500/20 rounded-lg">
                  <Brain className="w-6 h-6 text-blue-400" />
                </div>
                <div>
                  <h2 className="text-lg font-semibold text-white">{overview.learning_agent.role}</h2>
                  <p className="text-sm text-gray-500">{overview.learning_agent.description}</p>
                </div>
              </div>

              <div className="space-y-3">
                <div className="flex justify-between items-center">
                  <span className="text-gray-400">Status</span>
                  <span className={`px-2 py-1 rounded text-sm ${
                    overview.learning_agent.status === 'active' ? 'bg-green-500/20 text-green-400' : 'bg-gray-500/20 text-gray-400'
                  }`}>
                    {overview.learning_agent.status || 'idle'}
                  </span>
                </div>
                <div className="flex justify-between items-center">
                  <span className="text-gray-400">Mode</span>
                  <span className="text-white">{overview.learning_agent.mode || 'observing'}</span>
                </div>
                <div className="flex justify-between items-center">
                  <span className="text-gray-400">Strategy</span>
                  <StrategyBadge strategy={overview.learning_agent.current_strategy || 'conservative'} />
                </div>
                <div className="flex justify-between items-center">
                  <span className="text-gray-400">Observations</span>
                  <span className="text-white font-medium">{overview.learning_agent.total_observations}</span>
                </div>
                <div className="flex justify-between items-center">
                  <span className="text-gray-400">Actions Taken</span>
                  <span className="text-white font-medium">{overview.learning_agent.total_actions}</span>
                </div>
                <div className="flex justify-between items-center">
                  <span className="text-gray-400">Rules Created</span>
                  <span className="text-white font-medium">{overview.learning_agent.autonomous_rules_created}</span>
                </div>
              </div>
            </div>

            {/* Maverick Agent */}
            <div className="bg-dark-100 rounded-xl border border-dark-300 p-6">
              <div className="flex items-center gap-3 mb-4">
                <div className="p-3 bg-purple-500/20 rounded-lg">
                  <Zap className="w-6 h-6 text-purple-400" />
                </div>
                <div>
                  <h2 className="text-lg font-semibold text-white">{overview.maverick_agent.role}</h2>
                  <p className="text-sm text-gray-500">{overview.maverick_agent.description}</p>
                </div>
              </div>

              <div className="space-y-3">
                <div className="flex justify-between items-center">
                  <span className="text-gray-400">Mood</span>
                  <MoodIndicator mood={overview.maverick_agent.mood || 'curious'} />
                </div>
                <div className="flex justify-between items-center">
                  <span className="text-gray-400">Curiosity</span>
                  <div className="flex items-center gap-2">
                    <div className="w-24 h-2 bg-dark-300 rounded-full overflow-hidden">
                      <div
                        className="h-full bg-purple-500 rounded-full"
                        style={{ width: `${(overview.maverick_agent.curiosity || 0) * 100}%` }}
                      />
                    </div>
                    <span className="text-sm text-gray-400">{((overview.maverick_agent.curiosity || 0) * 100).toFixed(0)}%</span>
                  </div>
                </div>
                <div className="flex justify-between items-center">
                  <span className="text-gray-400">Confidence</span>
                  <div className="flex items-center gap-2">
                    <div className="w-24 h-2 bg-dark-300 rounded-full overflow-hidden">
                      <div
                        className="h-full bg-green-500 rounded-full"
                        style={{ width: `${(overview.maverick_agent.confidence || 0) * 100}%` }}
                      />
                    </div>
                    <span className="text-sm text-gray-400">{((overview.maverick_agent.confidence || 0) * 100).toFixed(0)}%</span>
                  </div>
                </div>
                <div className="flex justify-between items-center">
                  <span className="text-gray-400">Hypotheses</span>
                  <span className="text-white font-medium">{overview.maverick_agent.hypotheses_proposed}</span>
                </div>
                <div className="flex justify-between items-center">
                  <span className="text-gray-400">Validated</span>
                  <span className="text-green-400 font-medium">{overview.maverick_agent.hypotheses_validated}</span>
                </div>
                <div className="flex justify-between items-center">
                  <span className="text-gray-400">Applied</span>
                  <span className="text-purple-400 font-medium">{overview.maverick_agent.hypotheses_applied}</span>
                </div>
              </div>
            </div>
          </div>

          {/* Collaboration Section */}
          <div className="bg-gradient-to-r from-blue-500/10 to-purple-500/10 rounded-xl border border-purple-500/30 p-6">
            <h3 className="text-lg font-semibold text-white mb-2 flex items-center gap-2">
              <Sparkles className="w-5 h-5 text-yellow-400" />
              How They Work Together
            </h3>
            <p className="text-gray-300 mb-4">{overview.collaboration.description}</p>

            <div className="grid md:grid-cols-3 gap-4 mb-4">
              <StatCard
                label="Active Tests"
                value={overview.collaboration.active_tests}
                icon={FlaskConical}
                color="blue"
              />
              <StatCard
                label="Validated"
                value={overview.collaboration.maverick_hypotheses.validated}
                icon={CheckCircle}
                color="green"
              />
              <StatCard
                label="Applied"
                value={overview.collaboration.maverick_hypotheses.applied}
                icon={Rocket}
                color="purple"
              />
            </div>

            {overview.collaboration.recent_insights.length > 0 && (
              <div className="mt-4">
                <p className="text-sm text-gray-500 mb-2">Recent Insights:</p>
                <ul className="space-y-1">
                  {overview.collaboration.recent_insights.map((insight, i) => (
                    <li key={i} className="text-sm text-gray-300 flex items-start gap-2">
                      <Lightbulb className="w-4 h-4 text-yellow-400 mt-0.5 flex-shrink-0" />
                      {insight}
                    </li>
                  ))}
                </ul>
              </div>
            )}
          </div>
        </div>
      )}

      {/* Maverick Tab */}
      {activeTab === 'maverick' && hypotheses && (
        <div className="space-y-6">
          {/* Trigger Tasks */}
          <div className="bg-dark-100 rounded-xl border border-dark-300 p-6">
            <h3 className="text-lg font-semibold text-white mb-4">Trigger Maverick Tasks</h3>
            <div className="flex flex-wrap gap-3">
              {[
                { name: 'challenge_decisions', label: 'Challenge Decisions', icon: AlertTriangle },
                { name: 'test_hypotheses', label: 'Test Hypotheses', icon: FlaskConical },
                { name: 'measure_and_learn', label: 'Measure & Learn', icon: TrendingUp },
                { name: 'apply_improvements', label: 'Apply Improvements', icon: CheckCircle },
                { name: 'self_improve', label: 'Self Improve', icon: Brain }
              ].map(task => {
                const Icon = task.icon;
                return (
                  <button
                    key={task.name}
                    onClick={() => triggerTask('maverick', task.name)}
                    disabled={triggeringTask === task.name}
                    className="btn btn-secondary flex items-center gap-2"
                  >
                    {triggeringTask === task.name ? (
                      <Loader2 className="w-4 h-4 animate-spin" />
                    ) : (
                      <Icon className="w-4 h-4" />
                    )}
                    {task.label}
                  </button>
                );
              })}
            </div>
          </div>

          {/* Hypotheses */}
          <div className="grid md:grid-cols-3 gap-6">
            {/* Pending */}
            <div>
              <h3 className="text-lg font-semibold text-white mb-4 flex items-center gap-2">
                <Clock className="w-5 h-5 text-yellow-400" />
                Pending ({hypotheses.pending.length})
              </h3>
              <div className="space-y-3">
                {hypotheses.pending.length > 0 ? (
                  hypotheses.pending.map(h => (
                    <HypothesisCard key={h.id} hypothesis={h} type="pending" />
                  ))
                ) : (
                  <p className="text-gray-500 text-sm">No pending hypotheses</p>
                )}
              </div>
            </div>

            {/* Active Tests */}
            <div>
              <h3 className="text-lg font-semibold text-white mb-4 flex items-center gap-2">
                <FlaskConical className="w-5 h-5 text-blue-400" />
                Testing ({hypotheses.active_tests.length})
              </h3>
              <div className="space-y-3">
                {hypotheses.active_tests.length > 0 ? (
                  hypotheses.active_tests.map(h => (
                    <HypothesisCard key={h.id} hypothesis={h} type="testing" />
                  ))
                ) : (
                  <p className="text-gray-500 text-sm">No active tests</p>
                )}
              </div>
            </div>

            {/* Results */}
            <div>
              <h3 className="text-lg font-semibold text-white mb-4 flex items-center gap-2">
                <Target className="w-5 h-5 text-green-400" />
                Recent Results ({hypotheses.recent_results.length})
              </h3>
              <div className="space-y-3">
                {hypotheses.recent_results.length > 0 ? (
                  hypotheses.recent_results.map(h => (
                    <HypothesisCard key={h.id} hypothesis={h} type="result" />
                  ))
                ) : (
                  <p className="text-gray-500 text-sm">No recent results</p>
                )}
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Learning Agent Tab */}
      {activeTab === 'learning' && overview && (
        <div className="space-y-6">
          {/* Trigger Tasks */}
          <div className="bg-dark-100 rounded-xl border border-dark-300 p-6">
            <h3 className="text-lg font-semibold text-white mb-4">Trigger Learning Tasks</h3>
            <div className="flex flex-wrap gap-3">
              {[
                { name: 'observe_outcomes', label: 'Observe Outcomes', icon: Eye },
                { name: 'make_autonomous_decisions', label: 'Make Decisions', icon: Brain },
                { name: 'self_evaluate', label: 'Self Evaluate', icon: Target },
                { name: 'run_experiments', label: 'Run Experiments', icon: FlaskConical }
              ].map(task => {
                const Icon = task.icon;
                return (
                  <button
                    key={task.name}
                    onClick={() => triggerTask('learning', task.name)}
                    disabled={triggeringTask === task.name}
                    className="btn btn-secondary flex items-center gap-2"
                  >
                    {triggeringTask === task.name ? (
                      <Loader2 className="w-4 h-4 animate-spin" />
                    ) : (
                      <Icon className="w-4 h-4" />
                    )}
                    {task.label}
                  </button>
                );
              })}
            </div>
          </div>

          {/* Stats */}
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            <StatCard
              label="Observations"
              value={overview.learning_agent.total_observations}
              icon={Eye}
              color="blue"
            />
            <StatCard
              label="Actions Taken"
              value={overview.learning_agent.total_actions}
              icon={Activity}
              color="green"
            />
            <StatCard
              label="Rules Created"
              value={overview.learning_agent.autonomous_rules_created}
              icon={GraduationCap}
              color="purple"
            />
            <StatCard
              label="Strategy"
              value={overview.learning_agent.current_strategy || 'conservative'}
              icon={Shield}
              color="yellow"
            />
          </div>

          {/* Mode Description */}
          <div className="bg-dark-100 rounded-xl border border-dark-300 p-6">
            <h3 className="text-lg font-semibold text-white mb-4">Current Mode: {overview.learning_agent.mode}</h3>
            <div className="space-y-4">
              <div className="flex items-start gap-3">
                <div className="p-2 bg-blue-500/20 rounded-lg">
                  <Eye className="w-5 h-5 text-blue-400" />
                </div>
                <div>
                  <p className="font-medium text-white">Observing</p>
                  <p className="text-sm text-gray-400">Watching outcomes (kept vs deleted concepts) every 5 minutes</p>
                </div>
              </div>
              <div className="flex items-start gap-3">
                <div className="p-2 bg-green-500/20 rounded-lg">
                  <Brain className="w-5 h-5 text-green-400" />
                </div>
                <div>
                  <p className="font-medium text-white">Deciding</p>
                  <p className="text-sm text-gray-400">Making autonomous decisions every 10 minutes</p>
                </div>
              </div>
              <div className="flex items-start gap-3">
                <div className="p-2 bg-yellow-500/20 rounded-lg">
                  <Target className="w-5 h-5 text-yellow-400" />
                </div>
                <div>
                  <p className="font-medium text-white">Evaluating</p>
                  <p className="text-sm text-gray-400">Self-evaluating accuracy every hour</p>
                </div>
              </div>
              <div className="flex items-start gap-3">
                <div className="p-2 bg-purple-500/20 rounded-lg">
                  <FlaskConical className="w-5 h-5 text-purple-400" />
                </div>
                <div>
                  <p className="font-medium text-white">Experimenting</p>
                  <p className="text-sm text-gray-400">Running A/B tests every 6 hours</p>
                </div>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Rules Tab */}
      {activeTab === 'rules' && (
        <div className="space-y-6">
          <div className="flex justify-between items-center">
            <h3 className="text-lg font-semibold text-white">
              Learned Rules ({rules.length})
            </h3>
          </div>

          {rules.length > 0 ? (
            <div className="grid md:grid-cols-2 gap-4">
              {rules.map(rule => (
                <RuleCard key={rule.id} rule={rule} />
              ))}
            </div>
          ) : (
            <div className="text-center py-12 bg-dark-100 rounded-xl border border-dark-300">
              <GraduationCap className="w-12 h-12 mx-auto text-gray-600 mb-4" />
              <h3 className="text-lg font-medium text-gray-300">No learned rules yet</h3>
              <p className="text-gray-500 mt-2">
                The agents will create rules as they observe patterns and learn from outcomes.
              </p>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

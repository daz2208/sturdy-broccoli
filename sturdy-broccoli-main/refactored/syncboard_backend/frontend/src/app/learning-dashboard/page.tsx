'use client';

import { useEffect, useState } from 'react';
import api from '@/lib/api';
import toast from 'react-hot-toast';
import {
  Brain,
  TrendingUp,
  CheckCircle,
  XCircle,
  AlertCircle,
  Loader2,
  RefreshCw,
  PlayCircle,
  Target,
  Book,
  Lightbulb,
  BarChart3,
} from 'lucide-react';
import * as Types from '@/types/api';

export default function LearningDashboardPage() {
  const [activeTab, setActiveTab] = useState<'overview' | 'rules' | 'vocabulary'>('overview');
  const [learningStatus, setLearningStatus] = useState<Types.LearningStatus | null>(null);
  const [learningMetrics, setLearningMetrics] = useState<{ metrics: Types.LearningMetrics; interpretation: Record<string, string> } | null>(null);
  const [pendingValidations, setPendingValidations] = useState<Types.PendingValidations | null>(null);
  const [rules, setRules] = useState<any[]>([]);
  const [vocabulary, setVocabulary] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [runningLearning, setRunningLearning] = useState(false);
  const [calibrating, setCalibrating] = useState(false);

  useEffect(() => {
    loadDashboardData();
  }, []);

  const loadDashboardData = async () => {
    setLoading(true);
    try {
      const [status, metrics, validations, rulesData, vocabData] = await Promise.all([
        api.getLearningSystemStatus(),
        api.getLearningMetrics(),
        api.getPendingValidations(5),
        api.getLearnedRules(undefined, false),
        api.getVocabulary(),
      ]);
      setLearningStatus(status);
      setLearningMetrics(metrics);
      setPendingValidations(validations);
      setRules(rulesData.rules || []);
      setVocabulary(vocabData.vocabulary || []);
    } catch (err) {
      toast.error('Failed to load learning dashboard data');
    } finally {
      setLoading(false);
    }
  };

  const handleRunLearning = async () => {
    setRunningLearning(true);
    try {
      const result = await api.runLearning(90, 2);
      toast.success(`Learning complete! ${result.rules_created} rules created, ${result.rules_updated} updated`);
      loadDashboardData();
    } catch (err: any) {
      const errorMsg = err.response?.data?.detail || 'Learning run failed';
      toast.error(errorMsg);
    } finally {
      setRunningLearning(false);
    }
  };

  const handleCalibrate = async () => {
    setCalibrating(true);
    try {
      const result = await api.calibrateThresholds();
      toast.success(`Calibration complete! Thresholds: ${result.thresholds.high.toFixed(2)}, ${result.thresholds.medium.toFixed(2)}`);
      loadDashboardData();
    } catch (err: any) {
      const errorMsg = err.response?.data?.detail || 'Calibration failed';
      toast.error(errorMsg);
    } finally {
      setCalibrating(false);
    }
  };

  const handleValidation = async (decisionId: number, accepted: boolean) => {
    try {
      await api.validateAIDecision({
        ai_decision_id: decisionId,
        accepted,
        user_notes: accepted ? 'Validated as correct' : 'Rejected by user',
      });
      toast.success(accepted ? 'Decision validated' : 'Decision rejected');
      loadDashboardData();
    } catch (err) {
      toast.error('Validation failed');
    }
  };

  const handleDeactivateRule = async (ruleId: number) => {
    if (!confirm('Deactivate this rule?')) return;
    try {
      await api.deactivateLearnedRule(ruleId);
      toast.success('Rule deactivated');
      loadDashboardData();
    } catch (err) {
      toast.error('Failed to deactivate rule');
    }
  };

  const handleReactivateRule = async (ruleId: number) => {
    try {
      await api.reactivateLearnedRule(ruleId);
      toast.success('Rule reactivated');
      loadDashboardData();
    } catch (err) {
      toast.error('Failed to reactivate rule');
    }
  };

  const handleDeleteVocab = async (vocabId: number) => {
    if (!confirm('Delete this vocabulary term?')) return;
    try {
      await api.deleteVocabularyTerm(vocabId);
      toast.success('Vocabulary term deleted');
      loadDashboardData();
    } catch (err) {
      toast.error('Failed to delete vocabulary term');
    }
  };

  if (loading) {
    return (
      <div className="flex justify-center py-12">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary"></div>
      </div>
    );
  }

  return (
    <div className="space-y-6 animate-fadeIn max-w-7xl mx-auto">
      {/* Header */}
      <div>
        <h1 className="text-2xl font-bold text-gray-100 flex items-center gap-3">
          <Brain className="w-8 h-8 text-primary" />
          Learning Dashboard
        </h1>
        <p className="text-gray-500">Monitor AI learning system and provide feedback</p>
      </div>

      {/* Tabs */}
      <div className="flex gap-2 border-b border-dark-300">
        <button
          onClick={() => setActiveTab('overview')}
          className={`px-4 py-2 font-medium transition-colors ${
            activeTab === 'overview'
              ? 'text-primary border-b-2 border-primary'
              : 'text-gray-400 hover:text-gray-200'
          }`}
        >
          Overview
        </button>
        <button
          onClick={() => setActiveTab('rules')}
          className={`px-4 py-2 font-medium transition-colors ${
            activeTab === 'rules'
              ? 'text-primary border-b-2 border-primary'
              : 'text-gray-400 hover:text-gray-200'
          }`}
        >
          Rules ({rules.length})
        </button>
        <button
          onClick={() => setActiveTab('vocabulary')}
          className={`px-4 py-2 font-medium transition-colors ${
            activeTab === 'vocabulary'
              ? 'text-primary border-b-2 border-primary'
              : 'text-gray-400 hover:text-gray-200'
          }`}
        >
          Vocabulary ({vocabulary.length})
        </button>
      </div>

      {/* Overview Tab */}
      {activeTab === 'overview' && (
        <>
      {/* Quick Actions */}
      <div className="flex gap-3">
        <button
          onClick={handleRunLearning}
          disabled={runningLearning}
          className="btn btn-primary flex items-center gap-2"
        >
          {runningLearning ? <Loader2 className="w-4 h-4 animate-spin" /> : <PlayCircle className="w-4 h-4" />}
          Run Learning
        </button>
        <button
          onClick={handleCalibrate}
          disabled={calibrating}
          className="btn btn-secondary flex items-center gap-2"
        >
          {calibrating ? <Loader2 className="w-4 h-4 animate-spin" /> : <Target className="w-4 h-4" />}
          Calibrate Thresholds
        </button>
        <button
          onClick={loadDashboardData}
          className="btn btn-secondary flex items-center gap-2"
        >
          <RefreshCw className="w-4 h-4" />
          Refresh
        </button>
      </div>

      {/* Learning System Status */}
      {learningStatus && (
        <div className="bg-dark-100 rounded-xl border border-dark-300 p-6">
          <div className="flex items-center gap-3 mb-6">
            <Brain className="w-6 h-6 text-primary" />
            <h2 className="text-xl font-semibold text-gray-200">Learning System Status</h2>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4 mb-6">
            <div className="bg-dark-200 rounded-lg p-4">
              <p className="text-gray-500 text-sm mb-1">Active</p>
              <div className="flex items-center gap-2">
                {learningStatus.learning_active ? (
                  <>
                    <CheckCircle className="w-5 h-5 text-green-400" />
                    <span className="text-xl font-bold text-green-400">Yes</span>
                  </>
                ) : (
                  <>
                    <XCircle className="w-5 h-5 text-red-400" />
                    <span className="text-xl font-bold text-red-400">No</span>
                  </>
                )}
              </div>
            </div>

            <div className="bg-dark-200 rounded-lg p-4">
              <p className="text-gray-500 text-sm mb-1">Total Rules</p>
              <p className="text-2xl font-bold text-gray-100">{learningStatus.total_rules}</p>
            </div>

            <div className="bg-dark-200 rounded-lg p-4">
              <p className="text-gray-500 text-sm mb-1">Active Rules</p>
              <p className="text-2xl font-bold text-green-400">{learningStatus.active_rules}</p>
            </div>

            <div className="bg-dark-200 rounded-lg p-4">
              <p className="text-gray-500 text-sm mb-1">Vocabulary Terms</p>
              <p className="text-2xl font-bold text-primary">{learningStatus.vocabulary_count}</p>
            </div>
          </div>

          {/* Thresholds */}
          <div className="bg-dark-200 rounded-lg p-4">
            <p className="text-gray-400 text-sm font-semibold mb-3">Confidence Thresholds</p>
            <div className="grid grid-cols-3 gap-4">
              <div>
                <p className="text-gray-500 text-xs mb-1">High Confidence</p>
                <p className="text-lg font-bold text-green-400">{learningStatus.thresholds.high.toFixed(2)}</p>
              </div>
              <div>
                <p className="text-gray-500 text-xs mb-1">Medium Confidence</p>
                <p className="text-lg font-bold text-yellow-400">{learningStatus.thresholds.medium.toFixed(2)}</p>
              </div>
              <div>
                <p className="text-gray-500 text-xs mb-1">Low Confidence</p>
                <p className="text-lg font-bold text-red-400">{learningStatus.thresholds.low.toFixed(2)}</p>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Feedback Metrics */}
      {learningMetrics && (
        <div className="bg-dark-100 rounded-xl border border-dark-300 p-6">
          <div className="flex items-center gap-3 mb-6">
            <BarChart3 className="w-6 h-6 text-primary" />
            <h2 className="text-xl font-semibold text-gray-200">Feedback Metrics</h2>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4 mb-6">
            <div className="bg-dark-200 rounded-lg p-4">
              <p className="text-gray-500 text-sm mb-1">Total AI Decisions</p>
              <p className="text-2xl font-bold text-gray-100">{learningMetrics.metrics.total_ai_decisions}</p>
            </div>

            <div className="bg-dark-200 rounded-lg p-4">
              <p className="text-gray-500 text-sm mb-1">Acceptance Rate</p>
              <p className="text-2xl font-bold text-green-400">{(learningMetrics.metrics.acceptance_rate * 100).toFixed(1)}%</p>
            </div>

            <div className="bg-dark-200 rounded-lg p-4">
              <p className="text-gray-500 text-sm mb-1">Avg Confidence</p>
              <p className="text-2xl font-bold text-primary">{(learningMetrics.metrics.average_confidence * 100).toFixed(1)}%</p>
            </div>

            <div className="bg-dark-200 rounded-lg p-4">
              <p className="text-gray-500 text-sm mb-1">Unprocessed Feedback</p>
              <p className="text-2xl font-bold text-yellow-400">{learningMetrics.metrics.unprocessed_feedback}</p>
            </div>
          </div>

          {/* By Decision Type */}
          {Object.keys(learningMetrics.metrics.by_decision_type).length > 0 && (
            <div className="bg-dark-200 rounded-lg p-4">
              <p className="text-gray-400 text-sm font-semibold mb-3">By Decision Type</p>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                {Object.entries(learningMetrics.metrics.by_decision_type).map(([type, stats]) => (
                  <div key={type} className="bg-dark-100 rounded p-3">
                    <p className="text-gray-300 font-semibold mb-2 capitalize">{type.replace('_', ' ')}</p>
                    <div className="grid grid-cols-3 gap-2 text-xs">
                      <div>
                        <p className="text-gray-500">Total</p>
                        <p className="text-gray-200 font-bold">{stats.total}</p>
                      </div>
                      <div>
                        <p className="text-gray-500">Accepted</p>
                        <p className="text-green-400 font-bold">{stats.accepted}</p>
                      </div>
                      <div>
                        <p className="text-gray-500">Rejected</p>
                        <p className="text-red-400 font-bold">{stats.rejected}</p>
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Interpretation */}
          {learningMetrics.interpretation && Object.keys(learningMetrics.interpretation).length > 0 && (
            <div className="mt-4 p-4 bg-blue-900/20 border border-blue-700/50 rounded-lg">
              <p className="text-blue-300 text-sm font-semibold mb-2">Insights</p>
              <ul className="space-y-1">
                {Object.values(learningMetrics.interpretation).map((insight, idx) => (
                  <li key={idx} className="text-blue-200/80 text-sm flex items-start gap-2">
                    <Lightbulb className="w-4 h-4 mt-0.5 flex-shrink-0" />
                    {insight}
                  </li>
                ))}
              </ul>
            </div>
          )}
        </div>
      )}

      {/* Pending Validations */}
      {pendingValidations && pendingValidations.decisions.length > 0 && (
        <div className="bg-dark-100 rounded-xl border border-dark-300 p-6">
          <div className="flex items-center justify-between mb-6">
            <div className="flex items-center gap-3">
              <AlertCircle className="w-6 h-6 text-yellow-400" />
              <div>
                <h2 className="text-xl font-semibold text-gray-200">Pending Validations</h2>
                <p className="text-gray-500 text-sm">Low-confidence decisions needing review ({pendingValidations.total_pending} total)</p>
              </div>
            </div>
          </div>

          <div className="space-y-3">
            {pendingValidations.decisions.map((decision) => (
              <div key={decision.id} className="bg-dark-200 rounded-lg p-4">
                <div className="flex items-start justify-between gap-4">
                  <div className="flex-1">
                    <div className="flex items-center gap-2 mb-2">
                      <span className="px-2 py-1 bg-dark-100 rounded text-xs text-gray-400 capitalize">
                        {decision.decision_type.replace('_', ' ')}
                      </span>
                      <span className="text-xs text-gray-500">
                        Confidence: {(decision.confidence * 100).toFixed(1)}%
                      </span>
                      <span className="text-xs text-gray-500">
                        {new Date(decision.created_at).toLocaleDateString()}
                      </span>
                    </div>

                    <p className="text-gray-300 text-sm mb-2">{decision.reasoning}</p>

                    {decision.metadata && Object.keys(decision.metadata).length > 0 && (
                      <div className="mt-2 p-2 bg-dark-100 rounded">
                        <p className="text-gray-500 text-xs mb-1">Details:</p>
                        <div className="grid grid-cols-2 gap-2 text-xs">
                          {Object.entries(decision.metadata).map(([key, value]) => (
                            <div key={key}>
                              <span className="text-gray-500">{key}:</span>{' '}
                              <span className="text-gray-300">{String(value)}</span>
                            </div>
                          ))}
                        </div>
                      </div>
                    )}
                  </div>

                  <div className="flex gap-2">
                    <button
                      onClick={() => handleValidation(decision.id, true)}
                      className="p-2 bg-green-600 hover:bg-green-500 rounded text-white transition-colors"
                      title="Accept"
                    >
                      <CheckCircle className="w-5 h-5" />
                    </button>
                    <button
                      onClick={() => handleValidation(decision.id, false)}
                      className="p-2 bg-red-600 hover:bg-red-500 rounded text-white transition-colors"
                      title="Reject"
                    >
                      <XCircle className="w-5 h-5" />
                    </button>
                  </div>
                </div>
              </div>
            ))}
          </div>

          {pendingValidations.total_pending > 5 && (
            <p className="text-center text-gray-500 text-sm mt-4">
              Showing 5 of {pendingValidations.total_pending} pending validations
            </p>
          )}
        </div>
      )}

      {/* No Pending Validations */}
      {pendingValidations && pendingValidations.decisions.length === 0 && (
        <div className="bg-dark-100 rounded-xl border border-dark-300 p-6">
          <div className="flex items-center gap-3 mb-4">
            <CheckCircle className="w-6 h-6 text-green-400" />
            <h2 className="text-xl font-semibold text-gray-200">No Pending Validations</h2>
          </div>
          <p className="text-gray-400">All AI decisions are either high-confidence or already validated.</p>
        </div>
      )}

      {/* Help Text */}
      <div className="bg-dark-100 rounded-xl border border-dark-300 p-6">
        <div className="flex items-center gap-3 mb-4">
          <Book className="w-6 h-6 text-primary" />
          <h2 className="text-xl font-semibold text-gray-200">About Learning System</h2>
        </div>
        <div className="space-y-2 text-sm text-gray-400">
          <p>
            <strong className="text-gray-300">Run Learning:</strong> Analyzes your feedback to create and update rules for concept extraction and clustering.
          </p>
          <p>
            <strong className="text-gray-300">Calibrate Thresholds:</strong> Adjusts confidence thresholds based on your historical acceptance rates for better predictions.
          </p>
          <p>
            <strong className="text-gray-300">Pending Validations:</strong> Low-confidence AI decisions that need your review to improve future accuracy.
          </p>
        </div>
      </div>
        </>
      )}

      {/* Rules Tab */}
      {activeTab === 'rules' && (
        <div className="bg-dark-100 rounded-xl border border-dark-300 p-6">
          <h2 className="text-xl font-semibold text-gray-200 mb-4">Learned Rules</h2>
          {rules.length === 0 ? (
            <p className="text-gray-400 text-center py-8">No rules yet. Run learning to create rules from your feedback.</p>
          ) : (
            <div className="space-y-3">
              {rules.map((rule) => (
                <div key={rule.id} className="bg-dark-200 rounded-lg p-4">
                  <div className="flex justify-between items-start mb-2">
                    <div className="flex-1">
                      <div className="flex items-center gap-2 mb-2">
                        <span className="px-2 py-1 bg-dark-100 rounded text-xs font-medium text-primary capitalize">
                          {rule.type.replace('_', ' ')}
                        </span>
                        <span className="text-xs text-gray-500">
                          Confidence: {(rule.confidence * 100).toFixed(0)}%
                        </span>
                        <span className={`text-xs ${rule.active ? 'text-green-400' : 'text-gray-500'}`}>
                          {rule.active ? 'Active' : 'Inactive'}
                        </span>
                      </div>
                      <div className="text-sm text-gray-300 space-y-1">
                        <p><strong>Condition:</strong> {JSON.stringify(rule.condition)}</p>
                        <p><strong>Action:</strong> {JSON.stringify(rule.action)}</p>
                      </div>
                      <div className="flex gap-4 mt-2 text-xs text-gray-500">
                        <span>Applied: {rule.times_applied}</span>
                        <span>Overridden: {rule.times_overridden}</span>
                        <span>Created: {new Date(rule.created_at).toLocaleDateString()}</span>
                      </div>
                    </div>
                    <div className="flex gap-2">
                      {rule.active ? (
                        <button
                          onClick={() => handleDeactivateRule(rule.id)}
                          className="px-3 py-1 bg-red-600 hover:bg-red-500 rounded text-white text-sm transition-colors"
                        >
                          Deactivate
                        </button>
                      ) : (
                        <button
                          onClick={() => handleReactivateRule(rule.id)}
                          className="px-3 py-1 bg-green-600 hover:bg-green-500 rounded text-white text-sm transition-colors"
                        >
                          Reactivate
                        </button>
                      )}
                    </div>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {/* Vocabulary Tab */}
      {activeTab === 'vocabulary' && (
        <div className="bg-dark-100 rounded-xl border border-dark-300 p-6">
          <h2 className="text-xl font-semibold text-gray-200 mb-4">Concept Vocabulary</h2>
          {vocabulary.length === 0 ? (
            <p className="text-gray-400 text-center py-8">No vocabulary terms yet. Run learning to build vocabulary from your feedback.</p>
          ) : (
            <div className="space-y-3">
              {vocabulary.map((term) => (
                <div key={term.id} className="bg-dark-200 rounded-lg p-4">
                  <div className="flex justify-between items-start">
                    <div className="flex-1">
                      <div className="flex items-center gap-2 mb-2">
                        <h3 className="text-lg font-semibold text-gray-200">{term.canonical_name}</h3>
                        {term.category && (
                          <span className="px-2 py-1 bg-dark-100 rounded text-xs text-gray-400">{term.category}</span>
                        )}
                        {term.always_include && (
                          <span className="px-2 py-1 bg-green-900/30 text-green-400 rounded text-xs">Always Include</span>
                        )}
                        {term.never_include && (
                          <span className="px-2 py-1 bg-red-900/30 text-red-400 rounded text-xs">Never Include</span>
                        )}
                      </div>
                      {term.variants && term.variants.length > 0 && (
                        <p className="text-sm text-gray-400 mb-2">
                          <strong>Variants:</strong> {term.variants.join(', ')}
                        </p>
                      )}
                      <div className="flex gap-4 text-xs text-gray-500">
                        <span>Seen: {term.times_seen}</span>
                        <span>Kept: {term.times_kept}</span>
                        <span>Removed: {term.times_removed}</span>
                      </div>
                    </div>
                    <button
                      onClick={() => handleDeleteVocab(term.id)}
                      className="px-3 py-1 bg-red-600 hover:bg-red-500 rounded text-white text-sm transition-colors"
                    >
                      Delete
                    </button>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
}

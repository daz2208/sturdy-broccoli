'use client';

import { useEffect, useState } from 'react';
import api from '@/lib/api';
import toast from 'react-hot-toast';
import { CheckCircle, XCircle, AlertTriangle, Brain, TrendingUp, Info, Wifi, RefreshCw } from 'lucide-react';
import * as Types from '@/types/api';
import { useWebSocket } from '@/hooks/useWebSocket';

export default function AIValidationPage() {
  const [prompts, setPrompts] = useState<Types.ValidationPrompt[]>([]);
  const [summary, setSummary] = useState<Types.ValidationSummary | null>(null);
  const [metrics, setMetrics] = useState<Types.AccuracyMetrics | null>(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [submitting, setSubmitting] = useState<number | null>(null);

  // WebSocket for real-time updates
  const { isConnected, on } = useWebSocket();

  useEffect(() => {
    loadValidationData();

    // Listen for document events - new documents may create new decisions
    const unsubCreated = on('document_created', () => {
      // Delay slightly to allow backend to create AI decisions
      setTimeout(() => loadValidationData(), 2000);
    });

    // Listen for job completion events
    const unsubJobCompleted = on('job_completed', () => {
      // New document processed - may have new decisions
      setTimeout(() => loadValidationData(), 1000);
    });

    return () => {
      unsubCreated();
      unsubJobCompleted();
    };
  }, [on]);

  const loadValidationData = async () => {
    try {
      const [validationData, metricsData] = await Promise.all([
        api.getValidationPrompts(10),
        api.getAccuracyMetrics(),
      ]);

      setPrompts(validationData.prompts);
      setSummary(validationData.summary);
      setMetrics(metricsData);
    } catch (err) {
      toast.error('Failed to load validation data');
      console.error(err);
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  };

  const handleRefresh = () => {
    setRefreshing(true);
    loadValidationData();
  };

  const handleValidation = async (
    decisionId: number,
    result: 'accepted' | 'rejected' | 'partial',
    newValue?: Record<string, unknown>,
    reasoning?: string
  ) => {
    setSubmitting(decisionId);
    try {
      await api.submitFeedback({
        decision_id: decisionId,
        validation_result: result,
        new_value: newValue,
        user_reasoning: reasoning,
      });

      toast.success(
        result === 'accepted'
          ? '✅ Feedback accepted - AI is learning!'
          : '🔧 Feedback submitted - AI will improve!'
      );

      // Remove validated prompt from list
      setPrompts((prev) => prev.filter((p) => p.decision_id !== decisionId));

      // Reload metrics to show improvement
      const metricsData = await api.getAccuracyMetrics();
      setMetrics(metricsData);
    } catch (err) {
      toast.error('Failed to submit feedback');
      console.error(err);
    } finally {
      setSubmitting(null);
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
          <div className="flex items-center gap-3">
            <h1 className="text-2xl font-bold text-gray-100 flex items-center gap-3">
              <Brain className="w-7 h-7 text-primary" />
              AI Validation Dashboard
            </h1>
            {isConnected && (
              <span className="flex items-center gap-1 text-xs text-green-500 bg-green-500/10 px-2 py-1 rounded">
                <Wifi className="w-3 h-3" />
                Live
              </span>
            )}
          </div>
          <p className="text-gray-500 mt-1">
            Help the AI learn by validating low-confidence decisions
          </p>
        </div>
        <button
          onClick={handleRefresh}
          disabled={refreshing}
          className="btn btn-secondary p-2"
          title="Refresh validation data"
        >
          <RefreshCw className={`w-4 h-4 ${refreshing ? 'animate-spin' : ''}`} />
        </button>
      </div>

      {/* Summary Stats */}
      {summary && (
        <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
          <div className="bg-dark-100 rounded-xl border border-dark-300 p-4">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm text-gray-500">Pending Validations</p>
                <p className="text-2xl font-bold text-primary mt-1">{summary.total_pending}</p>
              </div>
              <AlertTriangle className="w-8 h-8 text-yellow-500 opacity-50" />
            </div>
          </div>

          <div className="bg-dark-100 rounded-xl border border-dark-300 p-4">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm text-gray-500">Avg Confidence</p>
                <p className="text-2xl font-bold text-accent-blue mt-1">
                  {Math.round(summary.average_confidence * 100)}%
                </p>
              </div>
              <TrendingUp className="w-8 h-8 text-blue-500 opacity-50" />
            </div>
          </div>

          <div className="bg-dark-100 rounded-xl border border-dark-300 p-4">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm text-gray-500">Urgency Level</p>
                <p className={`text-xl font-bold mt-1 ${getUrgencyColor(summary.urgency_level)}`}>
                  {summary.urgency_level.toUpperCase()}
                </p>
              </div>
              <Info className="w-8 h-8 text-gray-500 opacity-50" />
            </div>
          </div>

          <div className="bg-dark-100 rounded-xl border border-dark-300 p-4">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm text-gray-500">Overall Accuracy</p>
                <p className="text-2xl font-bold text-accent-green mt-1">
                  {metrics ? Math.round(metrics.overall_accuracy * 100) : 0}%
                </p>
              </div>
              <CheckCircle className="w-8 h-8 text-green-500 opacity-50" />
            </div>
          </div>
        </div>
      )}

      {/* Metrics Chart */}
      {metrics && metrics.validated_decisions > 0 && (
        <div className="bg-dark-100 rounded-xl border border-dark-300 p-6">
          <h2 className="text-lg font-semibold text-gray-200 mb-4">
            Accuracy by Confidence Range
          </h2>
          <div className="space-y-3">
            {Object.entries(metrics.by_confidence_range).map(([range, data]) => (
              <div key={range}>
                <div className="flex justify-between text-sm mb-1">
                  <span className="text-gray-400">{range}</span>
                  <span className="text-gray-300">
                    {Math.round(data.accuracy * 100)}% ({data.count} decisions)
                  </span>
                </div>
                <div className="w-full bg-dark-300 rounded-full h-2">
                  <div
                    className="bg-accent-green h-2 rounded-full transition-all"
                    style={{ width: `${data.accuracy * 100}%` }}
                  />
                </div>
              </div>
            ))}
          </div>
          <div className="mt-4 pt-4 border-t border-dark-300">
            <p className="text-sm text-gray-400">
              <strong className="text-gray-300">
                {metrics.validated_decisions}
              </strong>{' '}
              of{' '}
              <strong className="text-gray-300">{metrics.total_decisions}</strong>{' '}
              decisions validated
              {metrics.improvement_trend > 0 && (
                <span className="text-accent-green ml-2">
                  ↑ {Math.round(metrics.improvement_trend * 100)}% improvement
                </span>
              )}
            </p>
          </div>
        </div>
      )}

      {/* Validation Cards */}
      <div className="space-y-4">
        <h2 className="text-lg font-semibold text-gray-200">
          Decisions Needing Validation ({prompts.length})
        </h2>

        {prompts.length === 0 ? (
          <div className="bg-dark-100 rounded-xl border border-dark-300 p-12 text-center">
            <CheckCircle className="w-16 h-16 text-accent-green mx-auto mb-4 opacity-50" />
            <h3 className="text-xl font-semibold text-gray-200 mb-2">All Caught Up!</h3>
            <p className="text-gray-500">
              No low-confidence decisions need validation right now.
            </p>
            <p className="text-gray-500 text-sm mt-2">
              Upload documents to generate AI decisions for validation.
            </p>
          </div>
        ) : (
          prompts.map((prompt) => (
            <ValidationCard
              key={prompt.decision_id}
              prompt={prompt}
              onValidate={handleValidation}
              submitting={submitting === prompt.decision_id}
            />
          ))
        )}
      </div>
    </div>
  );
}

function ValidationCard({
  prompt,
  onValidate,
  submitting,
}: {
  prompt: Types.ValidationPrompt;
  onValidate: (
    decisionId: number,
    result: 'accepted' | 'rejected' | 'partial',
    newValue?: Record<string, unknown>,
    reasoning?: string
  ) => Promise<void>;
  submitting: boolean;
}) {
  const [showEditForm, setShowEditForm] = useState(false);
  const [editedConcepts, setEditedConcepts] = useState(
    prompt.concepts?.join(', ') || ''
  );
  const [reasoning, setReasoning] = useState('');

  const confidenceColor = getConfidenceColor(prompt.confidence);

  return (
    <div className="bg-dark-100 rounded-xl border border-dark-300 p-6">
      {/* Header */}
      <div className="flex items-start justify-between mb-4">
        <div className="flex-1">
          <h3 className="text-lg font-semibold text-gray-200">{prompt.title}</h3>
          <p className="text-gray-400 mt-1">{prompt.message}</p>
        </div>
        <div className={`px-3 py-1 rounded-full text-sm font-medium ${confidenceColor}`}>
          {Math.round(prompt.confidence * 100)}% confident
        </div>
      </div>

      {/* Concepts */}
      {prompt.concepts && prompt.concepts.length > 0 && (
        <div className="mb-4">
          <p className="text-sm text-gray-500 mb-2">Extracted Concepts:</p>
          <div className="flex flex-wrap gap-2">
            {prompt.concepts.map((concept, i) => (
              <span
                key={i}
                className="px-3 py-1 bg-dark-200 text-gray-300 rounded-full text-sm"
              >
                {concept}
              </span>
            ))}
          </div>
        </div>
      )}

      {/* Question */}
      <p className="text-gray-300 mb-4 font-medium">{prompt.question}</p>

      {/* Options */}
      {!showEditForm && (
        <div className="flex flex-wrap gap-3">
          {prompt.options.map((option) => (
            <button
              key={option.value}
              onClick={() => {
                if (option.requires_edit) {
                  setShowEditForm(true);
                } else {
                  onValidate(
                    prompt.decision_id,
                    option.feedback_type as 'accepted' | 'rejected'
                  );
                }
              }}
              disabled={submitting}
              className={`btn ${
                option.feedback_type === 'accepted'
                  ? 'btn-primary'
                  : option.feedback_type === 'rejected'
                  ? 'btn-danger'
                  : 'btn-secondary'
              } flex items-center gap-2 ${submitting ? 'opacity-50 cursor-not-allowed' : ''}`}
            >
              {option.feedback_type === 'accepted' && <CheckCircle className="w-4 h-4" />}
              {option.feedback_type === 'rejected' && <XCircle className="w-4 h-4" />}
              {option.feedback_type === 'partial' && <AlertTriangle className="w-4 h-4" />}
              {option.label}
            </button>
          ))}
        </div>
      )}

      {/* Edit Form */}
      {showEditForm && (
        <div className="mt-4 p-4 bg-dark-200 rounded-lg space-y-3">
          <div>
            <label className="block text-sm text-gray-400 mb-2">
              Corrected Concepts (comma-separated):
            </label>
            <input
              type="text"
              value={editedConcepts}
              onChange={(e) => setEditedConcepts(e.target.value)}
              className="input w-full"
              placeholder="Docker, Kubernetes, CI/CD"
            />
          </div>
          <div>
            <label className="block text-sm text-gray-400 mb-2">
              Optional: Why did you make this change?
            </label>
            <textarea
              value={reasoning}
              onChange={(e) => setReasoning(e.target.value)}
              className="input w-full h-20"
              placeholder="Explain your reasoning to help the AI learn better..."
            />
          </div>
          <div className="flex gap-3">
            <button
              onClick={() => {
                const concepts = editedConcepts
                  .split(',')
                  .map((c) => c.trim())
                  .filter((c) => c);
                onValidate(
                  prompt.decision_id,
                  'partial',
                  { concepts },
                  reasoning || undefined
                );
              }}
              disabled={submitting}
              className="btn btn-primary"
            >
              Submit Correction
            </button>
            <button
              onClick={() => setShowEditForm(false)}
              disabled={submitting}
              className="btn btn-secondary"
            >
              Cancel
            </button>
          </div>
        </div>
      )}

      {/* Metadata */}
      <div className="mt-4 pt-4 border-t border-dark-300 text-xs text-gray-500">
        Decision Type: {prompt.decision_type} • Created:{' '}
        {new Date(prompt.created_at).toLocaleString()}
      </div>
    </div>
  );
}

function getConfidenceColor(confidence: number): string {
  if (confidence >= 0.7) return 'bg-yellow-500/10 text-yellow-500';
  if (confidence >= 0.5) return 'bg-orange-500/10 text-orange-500';
  return 'bg-red-500/10 text-red-500';
}

function getUrgencyColor(urgency: string): string {
  if (urgency === 'high') return 'text-red-500';
  if (urgency === 'medium') return 'text-yellow-500';
  return 'text-green-500';
}

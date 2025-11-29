'use client';

import { useEffect, useState } from 'react';
import api from '@/lib/api';
import toast from 'react-hot-toast';
import {
  Target,
  Plus,
  Trash2,
  Edit3,
  Save,
  X,
  Star,
  TrendingUp,
  BookOpen,
  Briefcase,
  Cpu,
  Loader2,
  DollarSign,
  Clock,
  Users,
  Code2,
  Cloud
} from 'lucide-react';
import type { ProjectGoal } from '@/types/api';

const GOAL_TYPES = [
  { value: 'revenue', label: 'Revenue Generation', icon: DollarSign, color: 'text-green-400', bg: 'bg-green-500/10', border: 'border-green-500/20' },
  { value: 'learning', label: 'Learning & Skill Development', icon: BookOpen, color: 'text-blue-400', bg: 'bg-blue-500/10', border: 'border-blue-500/20' },
  { value: 'portfolio', label: 'Portfolio Building', icon: Briefcase, color: 'text-purple-400', bg: 'bg-purple-500/10', border: 'border-purple-500/20' },
  { value: 'automation', label: 'Automation & Productivity', icon: Cpu, color: 'text-orange-400', bg: 'bg-orange-500/10', border: 'border-orange-500/20' }
];

export default function GoalsPage() {
  const [goals, setGoals] = useState<ProjectGoal[]>([]);
  const [primaryGoal, setPrimaryGoal] = useState<ProjectGoal | null>(null);
  const [loading, setLoading] = useState(true);
  const [showCreateForm, setShowCreateForm] = useState(false);
  const [editingGoal, setEditingGoal] = useState<ProjectGoal | null>(null);

  // Form state
  const [formData, setFormData] = useState({
    goal_type: 'revenue',
    priority: 1,
    time_available: 'weekends',
    budget: '0',
    target_market: '',
    tech_stack_preference: '',
    deployment_preference: 'docker'
  });

  useEffect(() => {
    loadGoals();
  }, []);

  const loadGoals = async () => {
    setLoading(true);
    try {
      const [goalsData, primaryData] = await Promise.all([
        api.getProjectGoals(),
        api.getPrimaryGoal().catch(() => null)
      ]);
      setGoals(goalsData);
      setPrimaryGoal(primaryData);
    } catch (err) {
      toast.error('Failed to load goals');
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  const createGoal = async () => {
    try {
      const constraints = {
        time_available: formData.time_available,
        budget: parseInt(formData.budget) || 0,
        target_market: formData.target_market,
        tech_stack_preference: formData.tech_stack_preference,
        deployment_preference: formData.deployment_preference
      };

      await api.createProjectGoal(formData.goal_type, formData.priority, constraints);
      toast.success('Goal created!');
      setShowCreateForm(false);
      resetForm();
      loadGoals();
    } catch (err) {
      toast.error('Failed to create goal');
      console.error(err);
    }
  };

  const updateGoal = async () => {
    if (!editingGoal) return;

    try {
      const constraints = {
        time_available: formData.time_available,
        budget: parseInt(formData.budget) || 0,
        target_market: formData.target_market,
        tech_stack_preference: formData.tech_stack_preference,
        deployment_preference: formData.deployment_preference
      };

      await api.updateProjectGoal(editingGoal.id, {
        goal_type: formData.goal_type,
        priority: formData.priority,
        constraints
      });

      toast.success('Goal updated!');
      setEditingGoal(null);
      resetForm();
      loadGoals();
    } catch (err) {
      toast.error('Failed to update goal');
      console.error(err);
    }
  };

  const deleteGoal = async (goalId: number) => {
    if (!confirm('Delete this goal?')) return;

    try {
      await api.deleteProjectGoal(goalId);
      toast.success('Goal deleted');
      loadGoals();
    } catch (err) {
      toast.error('Failed to delete goal');
      console.error(err);
    }
  };

  const setPrimary = async (goalId: number) => {
    try {
      await api.setPrimaryProjectGoal(goalId);
      toast.success('Primary goal updated!');
      loadGoals();
    } catch (err) {
      toast.error('Failed to set primary goal');
      console.error(err);
    }
  };

  const startEdit = (goal: ProjectGoal) => {
    setEditingGoal(goal);
    setFormData({
      goal_type: goal.goal_type,
      priority: goal.priority,
      time_available: (goal.constraints?.time_available as string) || 'weekends',
      budget: String((goal.constraints?.budget as number) || 0),
      target_market: (goal.constraints?.target_market as string) || '',
      tech_stack_preference: (goal.constraints?.tech_stack_preference as string) || '',
      deployment_preference: (goal.constraints?.deployment_preference as string) || 'docker'
    });
    setShowCreateForm(false);
  };

  const resetForm = () => {
    setFormData({
      goal_type: 'revenue',
      priority: 1,
      time_available: 'weekends',
      budget: '0',
      target_market: '',
      tech_stack_preference: '',
      deployment_preference: 'docker'
    });
  };

  const cancelEdit = () => {
    setEditingGoal(null);
    setShowCreateForm(false);
    resetForm();
  };

  const getGoalTypeInfo = (type: string) => {
    return GOAL_TYPES.find(t => t.value === type) || GOAL_TYPES[0];
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <Loader2 className="w-8 h-8 animate-spin text-primary" />
      </div>
    );
  }

  return (
    <div className="space-y-6 animate-fadeIn">
      {/* Header */}
      <div className="flex items-start justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-100 flex items-center gap-3">
            <Target className="w-7 h-7 text-accent-green" />
            Project Goals
          </h1>
          <p className="text-gray-500 mt-1">
            Define your objectives to get personalized AI-driven build suggestions
          </p>
        </div>
        {!showCreateForm && !editingGoal && (
          <button
            onClick={() => setShowCreateForm(true)}
            className="btn btn-primary flex items-center gap-2"
          >
            <Plus className="w-4 h-4" />
            New Goal
          </button>
        )}
      </div>

      {/* Primary Goal Card */}
      {primaryGoal && !showCreateForm && !editingGoal && (
        <div className="bg-gradient-to-br from-primary/10 to-primary/5 rounded-xl border-2 border-primary/30 p-6">
          <div className="flex items-start justify-between">
            <div className="flex items-start gap-4">
              <div className="p-3 rounded-xl bg-primary/20">
                <Star className="w-6 h-6 text-primary" />
              </div>
              <div>
                <h2 className="text-lg font-semibold text-gray-100 flex items-center gap-2">
                  Primary Goal
                  <span className="badge badge-primary">Active</span>
                </h2>
                <p className="text-gray-300 mt-1">
                  {getGoalTypeInfo(primaryGoal.goal_type).label}
                </p>
                {primaryGoal.constraints && (
                  <div className="flex flex-wrap gap-2 mt-3 text-sm text-gray-400">
                    {primaryGoal.constraints.time_available !== undefined && (
                      <div className="flex items-center gap-1">
                        <Clock className="w-3 h-3" />
                        {String(primaryGoal.constraints.time_available)}
                      </div>
                    )}
                    {primaryGoal.constraints.budget !== undefined && (
                      <div className="flex items-center gap-1">
                        <DollarSign className="w-3 h-3" />
                        Budget: ${String(primaryGoal.constraints.budget)}
                      </div>
                    )}
                    {primaryGoal.constraints.tech_stack_preference !== undefined && (
                      <div className="flex items-center gap-1">
                        <Code2 className="w-3 h-3" />
                        {String(primaryGoal.constraints.tech_stack_preference)}
                      </div>
                    )}
                  </div>
                )}
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Create/Edit Form */}
      {(showCreateForm || editingGoal) && (
        <div className="bg-dark-100 rounded-xl border border-dark-300 p-6">
          <h2 className="text-lg font-semibold text-gray-200 mb-4 flex items-center gap-2">
            {editingGoal ? (
              <>
                <Edit3 className="w-5 h-5 text-primary" />
                Edit Goal
              </>
            ) : (
              <>
                <Plus className="w-5 h-5 text-accent-green" />
                Create New Goal
              </>
            )}
          </h2>

          <div className="space-y-4">
            {/* Goal Type */}
            <div>
              <label className="block text-sm font-medium text-gray-300 mb-2">
                Goal Type
              </label>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                {GOAL_TYPES.map((type) => {
                  const Icon = type.icon;
                  const isSelected = formData.goal_type === type.value;
                  return (
                    <button
                      key={type.value}
                      onClick={() => setFormData(prev => ({ ...prev, goal_type: type.value }))}
                      className={`p-4 rounded-lg border-2 transition-all text-left ${
                        isSelected
                          ? `${type.bg} ${type.border} ${type.color}`
                          : 'bg-dark-200 border-dark-300 text-gray-400 hover:border-primary/30'
                      }`}
                    >
                      <div className="flex items-center gap-3">
                        <Icon className="w-5 h-5" />
                        <span className="font-medium">{type.label}</span>
                      </div>
                    </button>
                  );
                })}
              </div>
            </div>

            {/* Priority */}
            <div>
              <label className="block text-sm font-medium text-gray-300 mb-2">
                Priority (higher = more important)
              </label>
              <input
                type="number"
                value={formData.priority}
                onChange={(e) => setFormData(prev => ({ ...prev, priority: parseInt(e.target.value) || 1 }))}
                className="input w-full"
                min="1"
                max="100"
              />
            </div>

            {/* Time Available */}
            <div>
              <label className="block text-sm font-medium text-gray-300 mb-2">
                <Clock className="w-4 h-4 inline mr-1" />
                Time Available
              </label>
              <select
                value={formData.time_available}
                onChange={(e) => setFormData(prev => ({ ...prev, time_available: e.target.value }))}
                className="input w-full"
              >
                <option value="weekends">Weekends Only</option>
                <option value="evenings">Evenings (2-3 hours/day)</option>
                <option value="part-time">Part-time (20 hours/week)</option>
                <option value="full-time">Full-time (40+ hours/week)</option>
              </select>
            </div>

            {/* Budget */}
            <div>
              <label className="block text-sm font-medium text-gray-300 mb-2">
                <DollarSign className="w-4 h-4 inline mr-1" />
                Budget (USD)
              </label>
              <input
                type="number"
                value={formData.budget}
                onChange={(e) => setFormData(prev => ({ ...prev, budget: e.target.value }))}
                className="input w-full"
                min="0"
                placeholder="0"
              />
            </div>

            {/* Target Market */}
            <div>
              <label className="block text-sm font-medium text-gray-300 mb-2">
                <Users className="w-4 h-4 inline mr-1" />
                Target Market (Optional)
              </label>
              <input
                type="text"
                value={formData.target_market}
                onChange={(e) => setFormData(prev => ({ ...prev, target_market: e.target.value }))}
                className="input w-full"
                placeholder="e.g., B2B SaaS, E-commerce, Developers"
              />
            </div>

            {/* Tech Stack Preference */}
            <div>
              <label className="block text-sm font-medium text-gray-300 mb-2">
                <Code2 className="w-4 h-4 inline mr-1" />
                Tech Stack Preference (Optional)
              </label>
              <input
                type="text"
                value={formData.tech_stack_preference}
                onChange={(e) => setFormData(prev => ({ ...prev, tech_stack_preference: e.target.value }))}
                className="input w-full"
                placeholder="e.g., Python/FastAPI, React/Next.js, Node.js"
              />
            </div>

            {/* Deployment Preference */}
            <div>
              <label className="block text-sm font-medium text-gray-300 mb-2">
                <Cloud className="w-4 h-4 inline mr-1" />
                Deployment Preference
              </label>
              <select
                value={formData.deployment_preference}
                onChange={(e) => setFormData(prev => ({ ...prev, deployment_preference: e.target.value }))}
                className="input w-full"
              >
                <option value="docker">Docker</option>
                <option value="vercel">Vercel</option>
                <option value="netlify">Netlify</option>
                <option value="aws">AWS</option>
                <option value="heroku">Heroku</option>
                <option value="digital-ocean">Digital Ocean</option>
              </select>
            </div>

            {/* Action Buttons */}
            <div className="flex gap-3 pt-4 border-t border-dark-300">
              <button
                onClick={editingGoal ? updateGoal : createGoal}
                className="btn btn-primary flex items-center gap-2"
              >
                <Save className="w-4 h-4" />
                {editingGoal ? 'Update Goal' : 'Create Goal'}
              </button>
              <button onClick={cancelEdit} className="btn btn-secondary">
                <X className="w-4 h-4 mr-2" />
                Cancel
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Goals List */}
      {!showCreateForm && !editingGoal && (
        <div className="space-y-4">
          <h2 className="text-lg font-semibold text-gray-200 flex items-center gap-2">
            <TrendingUp className="w-5 h-5 text-primary" />
            All Goals ({goals.length})
          </h2>

          {goals.length === 0 ? (
            <div className="bg-dark-100 rounded-xl border border-dark-300 p-12 text-center">
              <Target className="w-12 h-12 text-gray-600 mx-auto mb-3" />
              <p className="text-gray-400 mb-4">No goals yet. Create your first goal to get started!</p>
              <button
                onClick={() => setShowCreateForm(true)}
                className="btn btn-primary inline-flex items-center gap-2"
              >
                <Plus className="w-4 h-4" />
                Create Your First Goal
              </button>
            </div>
          ) : (
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              {goals.map((goal) => {
                const typeInfo = getGoalTypeInfo(goal.goal_type);
                const Icon = typeInfo.icon;
                const isPrimary = primaryGoal?.id === goal.id;

                return (
                  <div
                    key={goal.id}
                    className={`rounded-xl border p-5 transition-all ${
                      isPrimary
                        ? 'bg-primary/5 border-primary/30'
                        : 'bg-dark-100 border-dark-300 hover:border-primary/20'
                    }`}
                  >
                    <div className="flex items-start justify-between mb-3">
                      <div className="flex items-start gap-3">
                        <div className={`p-2 rounded-lg ${typeInfo.bg}`}>
                          <Icon className={`w-5 h-5 ${typeInfo.color}`} />
                        </div>
                        <div>
                          <h3 className="font-semibold text-gray-200 flex items-center gap-2">
                            {typeInfo.label}
                            {isPrimary && (
                              <Star className="w-4 h-4 text-primary fill-current" />
                            )}
                          </h3>
                          <p className="text-xs text-gray-500 mt-1">
                            Priority: {goal.priority}
                          </p>
                        </div>
                      </div>
                    </div>

                    {goal.constraints && (
                      <div className="space-y-2 text-sm text-gray-400 mb-4">
                        {goal.constraints.time_available !== undefined && (
                          <div className="flex items-center gap-2">
                            <Clock className="w-3 h-3" />
                            <span>{String(goal.constraints.time_available)}</span>
                          </div>
                        )}
                        {goal.constraints.budget !== undefined && (
                          <div className="flex items-center gap-2">
                            <DollarSign className="w-3 h-3" />
                            <span>Budget: ${String(goal.constraints.budget)}</span>
                          </div>
                        )}
                        {goal.constraints.target_market !== undefined && (
                          <div className="flex items-center gap-2">
                            <Users className="w-3 h-3" />
                            <span className="truncate">{String(goal.constraints.target_market)}</span>
                          </div>
                        )}
                        {goal.constraints.tech_stack_preference !== undefined && (
                          <div className="flex items-center gap-2">
                            <Code2 className="w-3 h-3" />
                            <span className="truncate">{String(goal.constraints.tech_stack_preference)}</span>
                          </div>
                        )}
                      </div>
                    )}

                    <div className="flex gap-2 pt-3 border-t border-dark-300">
                      {!isPrimary && (
                        <button
                          onClick={() => setPrimary(goal.id)}
                          className="btn btn-sm btn-secondary flex items-center gap-1"
                          title="Set as primary goal"
                        >
                          <Star className="w-3 h-3" />
                          Set Primary
                        </button>
                      )}
                      <button
                        onClick={() => startEdit(goal)}
                        className="btn btn-sm btn-secondary"
                        title="Edit goal"
                      >
                        <Edit3 className="w-3 h-3" />
                      </button>
                      <button
                        onClick={() => deleteGoal(goal.id)}
                        className="btn btn-sm btn-error"
                        title="Delete goal"
                      >
                        <Trash2 className="w-3 h-3" />
                      </button>
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </div>
      )}
    </div>
  );
}

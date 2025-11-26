'use client';
import { useState, useEffect } from 'react';
import api from '@/lib/api';
import toast from 'react-hot-toast';
import {
  Bookmark,
  Loader2,
  Trash2,
  Play,
  CheckCircle,
  Clock,
  Code,
  FolderTree,
  ListChecks,
  BookOpen,
  ChevronDown,
  ChevronRight,
  Filter,
  Sparkles,
  Target,
  AlertTriangle,
  ExternalLink,
  Edit3,
  Save,
  X,
  RefreshCw
} from 'lucide-react';

interface SavedIdea {
  id: number;
  idea_seed_id?: number;
  custom_title: string;
  custom_description: string;
  custom_data?: any;
  notes: string;
  status: 'saved' | 'started' | 'completed';
  created_at: string;
}

function StatusBadge({ status }: { status: string }) {
  const config = {
    saved: { icon: Bookmark, color: 'text-blue-400 bg-blue-500/20', label: 'Saved' },
    started: { icon: Play, color: 'text-yellow-400 bg-yellow-500/20', label: 'In Progress' },
    completed: { icon: CheckCircle, color: 'text-green-400 bg-green-500/20', label: 'Completed' }
  }[status] || { icon: Bookmark, color: 'text-gray-400 bg-gray-500/20', label: status };

  const Icon = config.icon;

  return (
    <span className={`px-3 py-1 rounded-full text-sm font-medium flex items-center gap-1 ${config.color}`}>
      <Icon className="w-3 h-3" />
      {config.label}
    </span>
  );
}

function IdeaCard({
  idea,
  onStatusChange,
  onDelete,
  onNotesUpdate
}: {
  idea: SavedIdea;
  onStatusChange: (id: number, status: string) => void;
  onDelete: (id: number) => void;
  onNotesUpdate: (id: number, notes: string) => void;
}) {
  const [expanded, setExpanded] = useState(false);
  const [editingNotes, setEditingNotes] = useState(false);
  const [notes, setNotes] = useState(idea.notes || '');

  const data = idea.custom_data || {};

  const saveNotes = () => {
    onNotesUpdate(idea.id, notes);
    setEditingNotes(false);
  };

  return (
    <div className="bg-dark-100 rounded-xl border border-dark-300 overflow-hidden">
      {/* Header */}
      <div className="p-6">
        <div className="flex justify-between items-start gap-4">
          <div className="flex-1">
            <div className="flex items-center gap-3 mb-2">
              <StatusBadge status={idea.status} />
              <span className="text-xs text-gray-500">
                <Clock className="w-3 h-3 inline mr-1" />
                {new Date(idea.created_at).toLocaleDateString()}
              </span>
            </div>
            <h3 className="text-xl font-semibold text-gray-100">{idea.custom_title}</h3>
            <p className="text-gray-400 mt-2">{idea.custom_description}</p>
          </div>

          {/* Actions */}
          <div className="flex items-center gap-2">
            {idea.status === 'saved' && (
              <button
                onClick={() => onStatusChange(idea.id, 'started')}
                className="btn btn-sm bg-yellow-500/20 text-yellow-400 hover:bg-yellow-500/30"
                title="Start working on this"
              >
                <Play className="w-4 h-4" />
              </button>
            )}
            {idea.status === 'started' && (
              <button
                onClick={() => onStatusChange(idea.id, 'completed')}
                className="btn btn-sm bg-green-500/20 text-green-400 hover:bg-green-500/30"
                title="Mark as completed"
              >
                <CheckCircle className="w-4 h-4" />
              </button>
            )}
            <button
              onClick={() => onDelete(idea.id)}
              className="btn btn-sm bg-red-500/20 text-red-400 hover:bg-red-500/30"
              title="Delete"
            >
              <Trash2 className="w-4 h-4" />
            </button>
          </div>
        </div>

        {/* Quick stats from saved data */}
        {data.required_skills && (
          <div className="mt-4">
            <p className="text-xs text-gray-500 uppercase tracking-wide mb-2">Tech Stack</p>
            <div className="flex flex-wrap gap-2">
              {data.required_skills.map((skill: string, i: number) => (
                <span key={i} className="badge badge-primary">{skill}</span>
              ))}
            </div>
          </div>
        )}

        {/* Quick info */}
        <div className="flex flex-wrap gap-3 mt-4">
          {data.effort_estimate && (
            <span className="px-3 py-1 rounded-full text-sm text-blue-400 bg-blue-500/20">
              <Clock className="w-3 h-3 inline mr-1" />
              {data.effort_estimate}
            </span>
          )}
          {data.complexity_level && (
            <span className="px-3 py-1 rounded-full text-sm text-purple-400 bg-purple-500/20">
              {data.complexity_level}
            </span>
          )}
          {data.feasibility && (
            <span className={`px-3 py-1 rounded-full text-sm ${
              data.feasibility === 'high' ? 'text-green-400 bg-green-500/20' :
              data.feasibility === 'medium' ? 'text-yellow-400 bg-yellow-500/20' :
              'text-red-400 bg-red-500/20'
            }`}>
              <Target className="w-3 h-3 inline mr-1" />
              {data.feasibility} feasibility
            </span>
          )}
        </div>

        {/* Notes section */}
        <div className="mt-4 p-3 bg-dark-200 rounded-lg">
          <div className="flex justify-between items-center mb-2">
            <p className="text-xs text-gray-500 uppercase tracking-wide">Your Notes</p>
            {!editingNotes ? (
              <button
                onClick={() => setEditingNotes(true)}
                className="text-gray-400 hover:text-white"
              >
                <Edit3 className="w-4 h-4" />
              </button>
            ) : (
              <div className="flex gap-2">
                <button onClick={saveNotes} className="text-green-400 hover:text-green-300">
                  <Save className="w-4 h-4" />
                </button>
                <button onClick={() => { setEditingNotes(false); setNotes(idea.notes || ''); }} className="text-red-400 hover:text-red-300">
                  <X className="w-4 h-4" />
                </button>
              </div>
            )}
          </div>
          {editingNotes ? (
            <textarea
              value={notes}
              onChange={(e) => setNotes(e.target.value)}
              className="w-full bg-dark-300 border border-dark-400 rounded p-2 text-gray-300 text-sm"
              rows={3}
              placeholder="Add your notes, progress, ideas..."
            />
          ) : (
            <p className="text-gray-400 text-sm">
              {idea.notes || 'No notes yet. Click edit to add some.'}
            </p>
          )}
        </div>
      </div>

      {/* Expand for full details */}
      {data.starter_code || data.file_structure || data.starter_steps ? (
        <>
          <button
            onClick={() => setExpanded(!expanded)}
            className="w-full px-6 py-3 flex items-center justify-center gap-2 text-accent-blue hover:bg-dark-200 transition-colors border-t border-dark-300"
          >
            {expanded ? (
              <>Hide Build Plan <ChevronDown className="w-4 h-4" /></>
            ) : (
              <>View Build Plan <ChevronRight className="w-4 h-4" /></>
            )}
          </button>

          {expanded && (
            <div className="p-6 space-y-4 border-t border-dark-300 bg-dark-50">
              {/* File Structure */}
              {data.file_structure && (
                <div className="border border-dark-400 rounded-lg overflow-hidden">
                  <div className="px-4 py-3 bg-dark-200 flex items-center gap-2 text-gray-300">
                    <FolderTree className="w-4 h-4 text-accent-blue" />
                    <span className="font-medium">Project Structure</span>
                  </div>
                  <pre className="p-4 bg-dark-100 overflow-x-auto text-sm">
                    <code className="text-gray-300 font-mono whitespace-pre">{data.file_structure}</code>
                  </pre>
                </div>
              )}

              {/* Starter Code */}
              {data.starter_code && (
                <div className="border border-dark-400 rounded-lg overflow-hidden">
                  <div className="px-4 py-3 bg-dark-200 flex items-center gap-2 text-gray-300">
                    <Code className="w-4 h-4 text-accent-blue" />
                    <span className="font-medium">Starter Code</span>
                  </div>
                  <pre className="p-4 bg-dark-100 overflow-x-auto text-sm">
                    <code className="text-gray-300 font-mono whitespace-pre">{data.starter_code}</code>
                  </pre>
                </div>
              )}

              {/* Starter Steps */}
              {data.starter_steps && data.starter_steps.length > 0 && (
                <div className="border border-dark-400 rounded-lg overflow-hidden">
                  <div className="px-4 py-3 bg-dark-200 flex items-center gap-2 text-gray-300">
                    <ListChecks className="w-4 h-4 text-accent-blue" />
                    <span className="font-medium">Step-by-Step Guide</span>
                  </div>
                  <div className="p-4 bg-dark-100">
                    <ol className="space-y-2">
                      {data.starter_steps.map((step: string, i: number) => (
                        <li key={i} className="flex items-start gap-3">
                          <span className="flex-shrink-0 w-6 h-6 rounded-full bg-accent-blue/20 text-accent-blue text-sm flex items-center justify-center font-medium">
                            {i + 1}
                          </span>
                          <span className="text-gray-300 pt-0.5">{step}</span>
                        </li>
                      ))}
                    </ol>
                  </div>
                </div>
              )}

              {/* Learning Path */}
              {data.learning_path && data.learning_path.length > 0 && (
                <div className="border border-dark-400 rounded-lg overflow-hidden">
                  <div className="px-4 py-3 bg-dark-200 flex items-center gap-2 text-gray-300">
                    <BookOpen className="w-4 h-4 text-accent-blue" />
                    <span className="font-medium">Learning Path</span>
                  </div>
                  <div className="p-4 bg-dark-100">
                    <ul className="space-y-2">
                      {data.learning_path.map((item: string, i: number) => (
                        <li key={i} className="flex items-start gap-2 text-gray-300">
                          <span className="text-accent-green">→</span>
                          {item}
                        </li>
                      ))}
                    </ul>
                  </div>
                </div>
              )}

              {/* Resources */}
              {data.recommended_resources && data.recommended_resources.length > 0 && (
                <div className="border border-dark-400 rounded-lg overflow-hidden">
                  <div className="px-4 py-3 bg-dark-200 flex items-center gap-2 text-gray-300">
                    <ExternalLink className="w-4 h-4 text-accent-blue" />
                    <span className="font-medium">Resources</span>
                  </div>
                  <div className="p-4 bg-dark-100">
                    <ul className="space-y-2">
                      {data.recommended_resources.map((resource: string, i: number) => (
                        <li key={i} className="text-accent-blue hover:underline cursor-pointer flex items-center gap-2">
                          <ExternalLink className="w-3 h-3" />
                          {resource}
                        </li>
                      ))}
                    </ul>
                  </div>
                </div>
              )}
            </div>
          )}
        </>
      ) : null}
    </div>
  );
}

export default function SavedIdeasPage() {
  const [ideas, setIdeas] = useState<SavedIdea[]>([]);
  const [loading, setLoading] = useState(true);
  const [filter, setFilter] = useState<string>('all');

  const loadIdeas = async () => {
    setLoading(true);
    try {
      const status = filter === 'all' ? undefined : filter;
      const data = await api.getSavedIdeas(status, 100);
      setIdeas(data.saved_ideas || []);
    } catch (err) {
      toast.error('Failed to load saved ideas');
    }
    setLoading(false);
  };

  useEffect(() => {
    loadIdeas();
  }, [filter]);

  const handleStatusChange = async (id: number, status: string) => {
    try {
      await api.updateSavedIdea(id, { status });
      toast.success(`Status updated to ${status}`);
      loadIdeas();
    } catch (err) {
      toast.error('Failed to update status');
    }
  };

  const handleDelete = async (id: number) => {
    if (!confirm('Are you sure you want to delete this idea?')) return;
    try {
      await api.deleteSavedIdea(id);
      toast.success('Idea deleted');
      loadIdeas();
    } catch (err) {
      toast.error('Failed to delete idea');
    }
  };

  const handleNotesUpdate = async (id: number, notes: string) => {
    try {
      await api.updateSavedIdea(id, { notes });
      toast.success('Notes saved');
      loadIdeas();
    } catch (err) {
      toast.error('Failed to save notes');
    }
  };

  const stats = {
    total: ideas.length,
    saved: ideas.filter(i => i.status === 'saved').length,
    started: ideas.filter(i => i.status === 'started').length,
    completed: ideas.filter(i => i.status === 'completed').length
  };

  return (
    <div className="space-y-6 animate-fadeIn">
      {/* Header */}
      <div className="flex flex-col md:flex-row justify-between items-start md:items-center gap-4">
        <div>
          <h1 className="text-2xl font-bold text-gray-100 flex items-center gap-2">
            <Bookmark className="w-6 h-6 text-accent-blue" />
            Saved Ideas
          </h1>
          <p className="text-gray-500 mt-1">
            Manage your bookmarked build ideas and track progress
          </p>
        </div>
        <div className="flex gap-3 items-center">
          <button
            onClick={loadIdeas}
            className="btn btn-ghost"
            title="Refresh"
          >
            <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} />
          </button>
          <select
            value={filter}
            onChange={(e) => setFilter(e.target.value)}
            className="input w-auto"
          >
            <option value="all">All Ideas ({stats.total})</option>
            <option value="saved">Saved ({stats.saved})</option>
            <option value="started">In Progress ({stats.started})</option>
            <option value="completed">Completed ({stats.completed})</option>
          </select>
        </div>
      </div>

      {/* Stats */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <div className="bg-dark-100 rounded-lg border border-dark-300 p-4">
          <p className="text-gray-500 text-sm">Total Ideas</p>
          <p className="text-2xl font-bold text-white">{stats.total}</p>
        </div>
        <div className="bg-dark-100 rounded-lg border border-dark-300 p-4">
          <p className="text-blue-400 text-sm flex items-center gap-1">
            <Bookmark className="w-3 h-3" /> Saved
          </p>
          <p className="text-2xl font-bold text-white">{stats.saved}</p>
        </div>
        <div className="bg-dark-100 rounded-lg border border-dark-300 p-4">
          <p className="text-yellow-400 text-sm flex items-center gap-1">
            <Play className="w-3 h-3" /> In Progress
          </p>
          <p className="text-2xl font-bold text-white">{stats.started}</p>
        </div>
        <div className="bg-dark-100 rounded-lg border border-dark-300 p-4">
          <p className="text-green-400 text-sm flex items-center gap-1">
            <CheckCircle className="w-3 h-3" /> Completed
          </p>
          <p className="text-2xl font-bold text-white">{stats.completed}</p>
        </div>
      </div>

      {/* Ideas list */}
      {loading ? (
        <div className="flex items-center justify-center py-16">
          <Loader2 className="w-8 h-8 animate-spin text-accent-blue" />
        </div>
      ) : ideas.length > 0 ? (
        <div className="space-y-6">
          {ideas.map((idea) => (
            <IdeaCard
              key={idea.id}
              idea={idea}
              onStatusChange={handleStatusChange}
              onDelete={handleDelete}
              onNotesUpdate={handleNotesUpdate}
            />
          ))}
        </div>
      ) : (
        <div className="text-center py-16 bg-dark-100 rounded-xl border border-dark-300">
          <Bookmark className="w-12 h-12 mx-auto text-gray-600 mb-4" />
          <h3 className="text-lg font-medium text-gray-300">No saved ideas yet</h3>
          <p className="text-gray-500 mt-2 max-w-md mx-auto">
            Go to <a href="/build" className="text-accent-blue hover:underline">Build Ideas</a> to generate project suggestions and save the ones you like.
          </p>
        </div>
      )}
    </div>
  );
}
